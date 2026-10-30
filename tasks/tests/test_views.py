import json
from datetime import date, timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

# Third party imports
from django.apps import apps
from django.contrib.messages import SUCCESS, get_messages
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

# Local folder imports
from chat.models import Message, Room
from tasks.models import Category, Task, TaskEvaluation, TaskSubtask, TaskVote
from tasks.tests.utils import make_task, make_user, task_form_data


class TaskNotificationSignalTest(TestCase):
    def setUp(self):
        dispatch = patch('core.notifications._dispatch_notification')
        self.dispatch = dispatch.start()
        self.addCleanup(dispatch.stop)

    def test_new_willing_helper_notifies_only_the_coordinator(self):
        coordinator = make_user('task-notification-coordinator')
        helper = make_user('task-notification-helper')
        task = make_task(created_by=coordinator, assigned_to=coordinator)
        self.dispatch.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            TaskVote.objects.create(task=task, user=helper, value=TaskVote.Value.UP)

        self.dispatch.assert_called_once()
        self.assertEqual(self.dispatch.call_args.kwargs['push_event'], 'task.helper_joined')
        self.assertEqual(self.dispatch.call_args.kwargs['recipient_ids'], {coordinator.pk})

    def test_task_status_change_notifies_its_coordinator(self):
        coordinator = make_user('task-status-coordinator')
        task = make_task(created_by=coordinator, assigned_to=coordinator)
        self.dispatch.reset_mock()
        task.status = Task.Status.COMPLETED

        with self.captureOnCommitCallbacks(execute=True):
            task.save(update_fields=['status'])

        self.dispatch.assert_called_once()
        self.assertEqual(self.dispatch.call_args.kwargs['push_event'], 'task.status_changed')
        self.assertEqual(self.dispatch.call_args.kwargs['recipient_ids'], {coordinator.pk})


class TaskListViewTest(TestCase):
    def setUp(self):
        notification_patch = patch('core.notifications._dispatch_notification')
        notification_patch.start()
        self.addCleanup(notification_patch.stop)
        self.client = Client()
        self.user = make_user("listuser")
        self.other_user = make_user("listother")

    def test_requires_login(self):
        response = self.client.get(reverse("tasks:list"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_returns_200(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:list"))
        self.assertEqual(response.status_code, 200)

    def test_ajax_returns_partial(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:list"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tasks/_task_list_partial.html")
        self.assertNotContains(response, "<html")

    def test_chat_room_pulse_tracks_seen_state_without_room_visibility_filters(self):
        unread = make_task(title="Unread", created_by=self.user)
        read = make_task(title="Read", created_by=self.user)
        empty = make_task(title="Empty", created_by=self.user)
        archived = make_task(title="Archived room", created_by=self.user)
        unlisted = make_task(title="Unlisted room", created_by=self.user)
        inbox = make_task(title="Inbox room", created_by=self.user)
        empty.chat_room = Room.objects.create(title="Empty task room")
        empty.save(update_fields=['chat_room'])
        read.chat_room.seen_by.add(self.user)
        archived.chat_room.archived = True
        archived.chat_room.save(update_fields=['archived'])
        unlisted.chat_room.public = False
        unlisted.chat_room.save(update_fields=['public'])
        unlisted.chat_room.allowed.clear()
        inbox.chat_room.is_inbox = True
        inbox.chat_room.save(update_fields=['is_inbox'])
        for task in (unread, read, archived, unlisted, inbox):
            Message.objects.create(room=task.chat_room, sender=self.other_user, text="Unread state")
        self.client.force_login(self.user)
        expected = {unread.pk: "tw-chat-room-pulse", read.pk: "", empty.pk: "", archived.pk: "tw-chat-room-pulse", unlisted.pk: "tw-chat-room-pulse", inbox.pk: "tw-chat-room-pulse"}

        response = self.client.get(reverse("tasks:list") + "?tab=awaiting")

        self.assertEqual(response.status_code, 200)
        self.assertEqual({task.pk: task.chat_room_pulse_class for task in response.context["awaiting_tasks"]}, expected)

        unread.chat_room.seen_by.add(self.user)
        read.chat_room.seen_by.remove(self.user)
        expected.update({unread.pk: "", read.pk: "tw-chat-room-pulse"})
        response = self.client.get(reverse("tasks:list") + "?tab=awaiting")

        self.assertEqual(response.status_code, 200)
        self.assertEqual({task.pk: task.chat_room_pulse_class for task in response.context["awaiting_tasks"]}, expected)


class TaskListFilteringTest(TestCase):
    """Sortowanie, filtr kategorii i przydział do zakładek — logika po stronie ORM."""

    def setUp(self):
        self.client = Client()
        self.user = make_user("filteruser")
        self.other = make_user("otheruser")
        self.cat = Category.objects.create(name="Kuchnia")
        self.client.login(username=self.user.username, password=self.user._plain_password)

    def upvote(self, task, user, value=TaskVote.Value.UP):
        return TaskVote.objects.create(task=task, user=user, value=value)

    def get_list(self, params=""):
        return self.client.get(reverse("tasks:list") + params)

    def test_awaiting_tab_shows_unassigned_and_low_score(self):
        make_task(title="Oczekujące")
        active = make_task(title="W realizacji", assigned_to=self.other, phase=Task.Phase.REALIZATION)
        self.upvote(active, self.user)
        self.upvote(active, self.other)
        response = self.get_list("?tab=awaiting")
        titles = [t.title for t in response.context["awaiting_tasks"]]
        self.assertIn("Oczekujące", titles)
        self.assertNotIn("W realizacji", titles)

    def test_active_tab_uses_explicit_realization_phase(self):
        no_owner = make_task(title="Bez koordynatora")
        owned_proposal = make_task(title="Propozycja z koordynatorem", assigned_to=self.other)
        realizing = make_task(title="Zadanie w realizacji", assigned_to=self.other, phase=Task.Phase.REALIZATION)
        for task in (no_owner, owned_proposal, realizing):
            self.upvote(task, self.user)
            self.upvote(task, self.other)
        response = self.get_list("?tab=active")
        titles = [task.title for task in response.context["active_tasks"]]
        self.assertEqual(titles, ["Zadanie w realizacji"])

    def test_task_detail_links_preserve_current_tab(self):
        awaiting = make_task(title="Oczekujące")
        active = make_task(title="W realizacji", assigned_to=self.other, phase=Task.Phase.REALIZATION)
        self.upvote(active, self.user)
        self.upvote(active, self.other)
        finished = make_task(title="Zakończone", status=Task.Status.COMPLETED)

        for tab, task in (("awaiting", awaiting), ("active", active), ("finished", finished)):
            with self.subTest(tab=tab):
                response = self.get_list(f"?tab={tab}")
                detail_url = reverse("tasks:detail", kwargs={"pk": task.pk})
                self.assertContains(response, f'data-detail-url="{detail_url}?tab={tab}"')

    def test_finished_tab_collects_tasks_with_one_more_opposing_vote(self):
        rejected = make_task(title="Odrzucone")
        self.upvote(rejected, self.user, TaskVote.Value.DOWN)
        supported = make_task(title="Równe głosy")
        self.upvote(supported, self.user, TaskVote.Value.DOWN)
        self.upvote(supported, self.other, TaskVote.Value.UP)
        response = self.get_list("?tab=finished")
        titles = [t.title for t in response.context["finished_rejected"]]
        self.assertIn("Odrzucone", titles)
        self.assertNotIn("Równe głosy", titles)
        self.assertEqual(response.context["finished_rejected"][0].priority_category, "rejected")

    def test_category_filter(self):
        in_cat = make_task(title="W kategorii")
        in_cat.category = self.cat
        in_cat.save()
        make_task(title="Bez kategorii")
        response = self.get_list(f"?tab=awaiting&category={self.cat.slug}")
        titles = [t.title for t in response.context["awaiting_tasks"]]
        self.assertIn("W kategorii", titles)
        self.assertNotIn("Bez kategorii", titles)

    def test_sort_by_score_uses_votes_up_not_votes_score(self):
        # 'Poparcie' = liczba helpers (votes_up); głosy sprzeciwu nie obniżają rankingu.
        more_helpers = make_task(title="Więcej helpers")
        better_net = make_task(title="Lepszy netto")
        voter3 = make_user("voter3")
        voter4 = make_user("voter4")
        for u in (self.user, self.other, voter3, voter4):
            self.upvote(more_helpers, u)
        TaskVote.objects.create(task=more_helpers, user=make_user("against"), value=TaskVote.Value.DOWN)
        for u in (self.user, self.other, voter3):
            self.upvote(better_net, u)
        response = self.get_list("?tab=awaiting&sort=score&order=desc")
        self.assertEqual(response.context["awaiting_tasks"][0].title, "Więcej helpers")

    def test_priority_uses_only_upvotes_and_older_task_wins_ties(self):
        highest = make_task(title="Najwięcej głosów Za")
        older = make_task(title="Starsze przy remisie")
        newer = make_task(title="Nowsze przy remisie")
        self.upvote(highest, self.user)
        self.upvote(highest, self.other)
        self.upvote(older, self.user)
        self.upvote(older, self.other, TaskVote.Value.DOWN)
        self.upvote(newer, self.user)
        Task.objects.filter(pk=older.pk).update(created_at="2020-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        Task.objects.filter(pk=newer.pk).update(created_at="2024-01-01T00:00:00Z", updated_at="2020-01-01T00:00:00Z")

        response = self.get_list("?tab=awaiting&sort=none")
        ordered_tasks = response.context["awaiting_tasks"]

        self.assertEqual([task.pk for task in ordered_tasks], [highest.pk, older.pk, newer.pk])
        self.assertEqual([task.priority_category for task in ordered_tasks], ["critical", "important", "beneficial"])

    def test_sort_by_date_asc(self):
        old = make_task(title="Starsze")
        new = make_task(title="Nowsze")
        Task.objects.filter(pk=old.pk).update(created_at="2020-01-01T00:00:00Z")
        Task.objects.filter(pk=new.pk).update(created_at="2024-01-01T00:00:00Z")
        response = self.get_list("?tab=awaiting&sort=date&order=asc")
        self.assertEqual(response.context["awaiting_tasks"][0].title, "Starsze")

    def test_mine_tab_shows_own_and_supported(self):
        make_task(title="Moje", assigned_to=self.user)
        supported = make_task(title="Wspierane")
        self.upvote(supported, self.user)
        make_task(title="Obce")
        response = self.get_list("?tab=mine")
        own_titles = [t.title for t in response.context["my_tasks_own"]]
        sup_titles = [t.title for t in response.context["my_tasks_supporting"]]
        self.assertEqual(own_titles, ["Moje"])
        self.assertEqual(sup_titles, ["Wspierane"])

    def test_mine_tab_supporting_shows_true_vote_counts(self):
        # Filtr pk__in (nie join na votes) — agregaty nie są zawężane do głosu usera.
        supported = make_task(title="Wspierane")
        self.upvote(supported, self.user)
        self.upvote(supported, self.other)
        response = self.get_list("?tab=mine")
        task = response.context["my_tasks_supporting"][0]
        self.assertEqual(task.votes_up, 2)
        self.assertEqual(task.user_vote_value, TaskVote.Value.UP)

    def test_stepper_contains_counts_for_each_task_tab(self):
        make_task(title="Moje", assigned_to=self.user)
        make_task(title="Oczekujące")
        active = make_task(title="Aktywne", assigned_to=self.other, phase=Task.Phase.REALIZATION)
        self.upvote(active, self.user)
        self.upvote(active, self.other)
        finished = make_task(title="Zakończone")
        finished.status = Task.Status.COMPLETED
        finished.save(update_fields=["status"])

        response = self.get_list("?tab=mine")

        self.assertEqual(response.context["task_counts"], {"mine": 2, "awaiting": 2, "active": 1, "finished": 1})
        self.assertContains(response, 'class="tw-stepper-step-count">2</span>', count=2)
        self.assertContains(response, 'class="tw-stepper-step-count">1</span>', count=2)


class TaskCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("creator")

    def test_requires_login(self):
        response = self.client.get(reverse("tasks:add"))
        self.assertEqual(response.status_code, 302)

    def test_get_returns_form(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="radio"', count=2)

    def test_post_creates_task(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), task_form_data(title="Nowe zadanie", description="Opis"))
        self.assertTrue(Task.objects.filter(title="Nowe zadanie").exists())

    def test_post_assigns_creator_as_created_by_and_assigned_to(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), task_form_data(title="Moje zadanie", description="Opis"))
        task = Task.objects.get(title="Moje zadanie")
        self.assertEqual(task.created_by, self.user)
        self.assertEqual(task.assigned_to, self.user)

    def test_post_creates_upvote_for_creator(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), task_form_data(title="Auto-vote", description="Opis"))
        task = Task.objects.get(title="Auto-vote")
        vote = TaskVote.objects.filter(task=task, user=self.user).first()
        self.assertIsNotNone(vote)
        self.assertEqual(vote.value, TaskVote.Value.UP)

    def test_post_empty_title_returns_form(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:add"), task_form_data(title="", description="Opis"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.exists())


class TaskDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("detailuser")
        self.task = make_task(created_by=self.user)

    def test_requires_login(self):
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_returns_200(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)

    def test_proposal_explains_automatic_start_without_a_manual_button(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        message = gettext("Realization starts automatically when the vote balance reaches %(threshold)s and the full team is assembled.")
        self.assertContains(response, message % {"threshold": Task.REALIZATION_VOTE_THRESHOLD})
        self.assertNotContains(response, f"/tasks/{self.task.pk}/start/")
        self.assertContains(response, gettext("Tasks"))
        self.assertNotContains(response, "Subtasks")

    def test_realization_explains_automatic_return_without_a_manual_button(self):
        self.task.phase = Task.Phase.REALIZATION
        self.task.save(update_fields=["phase"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        message = gettext("The activity automatically returns to proposal if vote, coordinator, or team requirements are no longer met; votes and team are kept.")
        self.assertContains(response, message)
        self.assertNotContains(response, "returnToProposalModal")

    def test_nonexistent_task_returns_404(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)

    def test_detail_labels_unassigned_active_task_as_awaiting(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        expected_label = gettext("Awaiting")
        self.assertEqual(str(response.context["task_status_label"]), expected_label)
        self.assertContains(response, expected_label)

    def test_detail_labels_assigned_supported_task_as_in_progress(self):
        coordinator = make_user("detailcoordinator")
        self.task.assigned_to = coordinator
        self.task.phase = Task.Phase.REALIZATION
        self.task.save(update_fields=["assigned_to", "phase"])
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=coordinator, value=TaskVote.Value.UP)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        expected_label = gettext("In progress")
        self.assertEqual(str(response.context["task_status_label"]), expected_label)
        self.assertContains(response, expected_label)

    def test_detail_keeps_terminal_status_label(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save(update_fields=["status"])
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(str(response.context["task_status_label"]), gettext("Completed"))


class TaskEditViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = make_user("owner")
        self.other = make_user("intruder")
        self.task = make_task(created_by=self.owner, assigned_to=self.owner)

    def test_assigned_user_can_access_edit(self):
        self.client.login(username=self.owner.username, password=self.owner._plain_password)
        response = self.client.get(reverse("tasks:edit", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)

    def test_non_assigned_user_redirected_to_detail(self):
        self.client.login(username=self.other.username, password=self.other._plain_password)
        detail_url = reverse("tasks:detail", kwargs={"pk": self.task.pk})
        response = self.client.get(reverse("tasks:edit", kwargs={"pk": self.task.pk}))
        self.assertRedirects(response, detail_url)
        response = self.client.post(reverse("tasks:edit", kwargs={"pk": self.task.pk}), {"title": "Intruder edit", "description": "Not allowed"})
        self.assertRedirects(response, detail_url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Zadanie")

    def test_anonymous_user_cannot_access_edit(self):
        client = Client()
        url = reverse("tasks:edit", kwargs={"pk": self.task.pk})

        self.assertEqual(client.get(url).status_code, 302)
        self.assertEqual(client.post(url, {"title": "Anonymous edit"}).status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Zadanie")

    def test_inactive_task_cannot_be_edited(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save(update_fields=['status'])
        self.client.force_login(self.owner)
        detail_url = reverse('tasks:detail', kwargs={'pk': self.task.pk})
        edit_url = reverse('tasks:edit', kwargs={'pk': self.task.pk})

        self.assertRedirects(self.client.get(edit_url), detail_url)
        self.assertRedirects(self.client.post(edit_url, {'title': 'Inactive edit'}), detail_url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Zadanie')

    def test_edit_updates_title(self):
        self.client.login(username=self.owner.username, password=self.owner._plain_password)
        response = self.client.post(reverse("tasks:edit", kwargs={"pk": self.task.pk}), task_form_data(title="Zmieniony tytuł", description="Nowy opis"))
        self.assertEqual([message.level for message in get_messages(response.wsgi_request)], [SUCCESS])
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Zmieniony tytuł")

    def test_realization_edit_form_only_exposes_planning_metadata(self):
        self.task.phase = Task.Phase.REALIZATION
        self.task.save(update_fields=["phase"])
        self.client.force_login(self.owner)
        response = self.client.get(reverse("tasks:edit", kwargs={"pk": self.task.pk}))
        self.assertEqual(set(response.context["form"].fields), {"due_date", "category"})

    def test_realization_edit_only_updates_planning_details_without_resetting_votes(self):
        self.task.phase = Task.Phase.REALIZATION
        self.task.save(update_fields=["phase"])
        TaskVote.objects.create(task=self.task, user=self.owner, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=self.other, value=TaskVote.Value.UP)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("tasks:edit", kwargs={"pk": self.task.pk}), {"due_date": "2026-11-20", "category": "", "title": "Nie zmieniaj"})
        self.assertEqual(response.status_code, 302, response.context["form"].errors if response.status_code == 200 else "")
        self.assertEqual(response.url, reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Zadanie")
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)
        self.assertEqual(self.task.due_date, date(2026, 11, 20))
        self.assertTrue(TaskVote.objects.filter(task=self.task, user=self.owner).exists())

    def test_proposal_edit_does_not_reset_votes(self):
        TaskVote.objects.create(task=self.task, user=self.owner, value=TaskVote.Value.UP)
        self.client.force_login(self.owner)
        self.client.post(reverse("tasks:edit", kwargs={"pk": self.task.pk}), task_form_data(title="Nowy tytuł"))
        self.assertTrue(TaskVote.objects.filter(task=self.task, user=self.owner, value=TaskVote.Value.UP).exists())

    def test_edit_invalid_title_rerenders_form_without_saving(self):
        self.client.login(username=self.owner.username, password=self.owner._plain_password)
        response = self.client.post(reverse("tasks:edit", kwargs={"pk": self.task.pk}), task_form_data(title="", description="Nowy opis"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Zadanie")


class TaskCloseViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = make_user("owner")
        self.other = make_user("intruder")
        self.task = make_task(created_by=self.owner, assigned_to=self.owner)

    def test_assigned_user_can_access_close(self):
        self.client.login(username=self.owner.username, password=self.owner._plain_password)
        response = self.client.get(reverse("tasks:close", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)

    def test_non_assigned_user_redirected_to_detail(self):
        self.client.login(username=self.other.username, password=self.other._plain_password)
        response = self.client.get(reverse("tasks:close", kwargs={"pk": self.task.pk}))
        self.assertRedirects(response, reverse("tasks:detail", kwargs={"pk": self.task.pk}))

    def test_close_sets_completed_status(self):
        self.client.login(username=self.owner.username, password=self.owner._plain_password)
        self.client.post(reverse("tasks:close", kwargs={"pk": self.task.pk}), {"status": Task.Status.COMPLETED})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.COMPLETED)

    def test_close_sets_cancelled_status(self):
        self.client.login(username=self.owner.username, password=self.owner._plain_password)
        self.client.post(reverse("tasks:close", kwargs={"pk": self.task.pk}), {"status": Task.Status.CANCELLED})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.CANCELLED)


class TakeResignTaskTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("worker")
        self.other = make_user("other")
        self.task = make_task(created_by=self.other)

    def test_take_task_assigns_user(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:take", kwargs={"pk": self.task.pk}))
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to, self.user)

    def test_take_task_rejects_completed_task(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save(update_fields=["status"])
        self.client.login(username=self.user.username, password=self.user._plain_password)

        response = self.client.post(reverse("tasks:take", kwargs={"pk": self.task.pk}))

        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to)

    def test_take_task_rejects_external_next_url(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)

        response = self.client.post(reverse("tasks:take", kwargs={"pk": self.task.pk}), {"next": "https://evil.example/"})

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, "https://evil.example/")

    def test_take_task_requires_post(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:take", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 405)

    def test_resign_task_clears_assigned_to(self):
        self.task.assigned_to = self.user
        self.task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}))
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to)

    def test_resign_by_non_assigned_user_does_nothing(self):
        self.task.assigned_to = self.other
        self.task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}))
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to, self.other)

    def test_take_task_ajax_returns_user_data(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:take", kwargs={"pk": self.task.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIsNotNone(data["assigned_to"])
        self.assertEqual(data["assigned_to"]["id"], self.user.id)
        self.assertEqual(data["assigned_to"]["username"], self.user.username)

    def test_resign_task_ajax_returns_null_assigned_to(self):
        self.task.assigned_to = self.user
        self.task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIsNone(data["assigned_to"])

    def test_resign_task_ajax_403_if_not_coordinator(self):
        self.task.assigned_to = self.other
        self.task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)

    def test_resign_unassigned_task_does_nothing(self):
        # assigned_to=None — nikomu nie przypisane, resign nie powinien crashować
        self.assertIsNone(self.task.assigned_to)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}))
        self.assertIn(response.status_code, (302, 200))
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to)

    def test_resign_promotes_earliest_willing_helper_even_if_not_approved(self):
        helper = make_user("helper")
        later_helper = make_user("laterhelper")
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=later_helper, value=TaskVote.Value.UP)
        now = timezone.now()
        TaskVote.objects.filter(task=self.task, user=self.user).update(updated_at=now - timedelta(days=3))
        TaskVote.objects.filter(task=self.task, user=helper).update(updated_at=now - timedelta(days=2))
        TaskVote.objects.filter(task=self.task, user=later_helper).update(updated_at=now - timedelta(days=1))
        self.task.approved_helpers.add(later_helper)
        self.task.assigned_to = self.user
        self.task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)

        response = self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to, helper)
        self.assertEqual(data["assigned_to"]["id"], helper.pk)
        self.assertFalse(data["is_coordinator"])
        self.assertFalse(data["in_team"])
        self.assertTrue(self.task.is_user_approved(helper))
        self.assertTrue(self.task.approved_helpers.filter(pk=later_helper.pk).exists())

    def test_former_coordinator_remains_eligible_for_later_succession(self):
        helper = make_user("helper")
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.UP)
        self.task.assigned_to = self.user
        self.task.save()

        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}))
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to, helper)

        self.client.login(username=helper.username, password=helper._plain_password)
        self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}))
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to, self.user)

    def test_resign_keeps_ex_coordinator_in_team(self):
        # Koordynator będący wcześniej zatwierdzonym pomocnikiem zostaje w zespole.
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        self.task.approved_helpers.add(self.user)
        self.task.assigned_to = self.user
        self.task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to)
        self.assertTrue(response.json()["in_team"])
        self.assertTrue(self.task.approved_helpers.filter(pk=self.user.pk).exists())


class VoteTaskTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("voter")
        self.task = make_task(created_by=self.user)

    def test_upvote_creates_vote(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": 1})
        self.assertTrue(TaskVote.objects.filter(task=self.task, user=self.user, value=1).exists())

    def test_downvote_creates_vote(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.assertTrue(TaskVote.objects.filter(task=self.task, user=self.user, value=-1).exists())

    def test_same_vote_twice_removes_vote(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": 1})
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": 1})
        self.assertFalse(TaskVote.objects.filter(task=self.task, user=self.user).exists())

    def test_flip_vote_up_to_down(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": 1})
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        vote = TaskVote.objects.get(task=self.task, user=self.user)
        self.assertEqual(vote.value, TaskVote.Value.DOWN)

    def test_flip_vote_down_to_up(self):
        helper = make_user("flip-vote-helper")
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.UP)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": 1})
        vote = TaskVote.objects.get(task=self.task, user=self.user)
        self.assertEqual(vote.value, TaskVote.Value.UP)

    def test_one_more_opposing_vote_rejects_task(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.REJECTED)

    def test_equal_support_and_opposition_do_not_reject_task(self):
        helper = make_user("supporting-voter")
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.UP)
        self.client.force_login(self.user)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.ACTIVE)

    def test_one_more_opposing_vote_rejects_task_during_realization(self):
        self.task.phase = Task.Phase.REALIZATION
        self.task.assigned_to = self.user
        self.task.save(update_fields=["phase", "assigned_to"])
        self.client.force_login(self.user)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.REJECTED)
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)

    def test_invalid_vote_value_redirects_without_saving(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": 99})
        self.assertFalse(TaskVote.objects.filter(task=self.task, user=self.user).exists())

    def test_requires_post(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:vote", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 405)


class ReopenDeleteTaskTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("owner")
        self.task = make_task(created_by=self.user, status=Task.Status.COMPLETED)

    def test_reopen_changes_status_to_active(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:reopen", kwargs={"pk": self.task.pk}))
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.ACTIVE)

    def test_reopen_resets_votes_and_phase_but_preserves_team(self):
        helper = make_user("reopen-helper")
        self.task.assigned_to = self.user
        self.task.phase = Task.Phase.REALIZATION
        self.task.save(update_fields=["assigned_to", "phase"])
        self.task.approved_helpers.add(helper)
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.DOWN)
        self.client.force_login(self.user)

        self.client.post(reverse("tasks:reopen", kwargs={"pk": self.task.pk}))

        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.PROPOSAL)
        self.assertEqual(self.task.assigned_to, self.user)
        self.assertTrue(self.task.approved_helpers.filter(pk=helper.pk).exists())
        self.assertFalse(TaskVote.objects.filter(task=self.task).exists())

    def test_reopen_already_active_task_does_nothing(self):
        active_task = make_task(created_by=self.user, status=Task.Status.ACTIVE)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:reopen", kwargs={"pk": active_task.pk}))
        active_task.refresh_from_db()
        self.assertEqual(active_task.status, Task.Status.ACTIVE)

    def test_reopen_by_unrelated_user_is_denied(self):
        other = make_user("reopen_intruder")
        self.client.login(username=other.username, password=other._plain_password)

        response = self.client.post(reverse("tasks:reopen", kwargs={"pk": self.task.pk}))

        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.COMPLETED)

    def test_delete_task_by_creator(self):
        active_task = make_task(created_by=self.user, status=Task.Status.ACTIVE)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:delete", kwargs={"pk": active_task.pk}))
        self.assertFalse(Task.objects.filter(pk=active_task.pk).exists())

    def test_delete_completed_task_not_allowed(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:delete", kwargs={"pk": self.task.pk}))
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_delete_by_non_creator_not_allowed(self):
        other = make_user("intruder")
        active_task = make_task(created_by=self.user, status=Task.Status.ACTIVE)
        self.client.login(username=other.username, password=other._plain_password)
        self.client.post(reverse("tasks:delete", kwargs={"pk": active_task.pk}))
        self.assertTrue(Task.objects.filter(pk=active_task.pk).exists())


class TaskPhaseTransitionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.coordinator = make_user("phase-coordinator")
        self.helper = make_user("phase-helper")
        self.other = make_user("phase-other")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, required_people=2)

    def cast_support_vote(self, user):
        self.client.force_login(user)
        return self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": TaskVote.Value.UP}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_vote_threshold_automatically_starts_when_team_is_ready(self):
        self.task.required_people = 1
        self.task.save(update_fields=["required_people"])
        self.cast_support_vote(self.coordinator)
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.PROPOSAL)

        response = self.cast_support_vote(self.helper)
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)
        self.assertEqual(response.json()["phase"], Task.Phase.REALIZATION)

    def test_waits_for_approved_team_then_starts_automatically(self):
        self.cast_support_vote(self.coordinator)
        self.cast_support_vote(self.helper)
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.PROPOSAL)

        self.client.force_login(self.coordinator)
        response = self.client.post(reverse("tasks:toggle_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)
        self.assertEqual(response.json()["phase"], Task.Phase.REALIZATION)

    def test_legacy_task_without_people_requirement_uses_coordinator_as_team(self):
        self.task.required_people = None
        self.task.save(update_fields=["required_people"])
        self.cast_support_vote(self.coordinator)
        self.cast_support_vote(self.helper)
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)

    def test_coordinator_assignment_can_complete_start_requirements(self):
        self.task.assigned_to = None
        self.task.required_people = 1
        self.task.save(update_fields=["assigned_to", "required_people"])
        self.task.approved_helpers.add(self.helper)
        self.cast_support_vote(self.helper)
        self.cast_support_vote(self.other)
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.PROPOSAL)

        self.client.force_login(self.coordinator)
        response = self.client.post(reverse("tasks:take", kwargs={"pk": self.task.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)
        self.assertEqual(response.json()["phase"], Task.Phase.REALIZATION)

    def test_editing_team_size_can_complete_start_requirements(self):
        self.cast_support_vote(self.coordinator)
        self.cast_support_vote(self.helper)
        self.client.force_login(self.coordinator)
        self.client.post(reverse("tasks:edit", kwargs={"pk": self.task.pk}), task_form_data(required_people="1"))
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)

    def test_vote_and_team_requirements_must_both_be_met(self):
        self.client.force_login(self.coordinator)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": TaskVote.Value.UP})
        self.client.force_login(self.helper)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": TaskVote.Value.UP})
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.PROPOSAL)

    def test_losing_vote_support_returns_to_proposal_and_preserves_team(self):
        self.task.phase = Task.Phase.REALIZATION
        self.task.save(update_fields=["phase"])
        TaskVote.objects.create(task=self.task, user=self.coordinator, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=self.helper, value=TaskVote.Value.UP)
        self.task.approved_helpers.add(self.helper)

        response = self.cast_support_vote(self.helper)
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.PROPOSAL)
        self.assertEqual(response.json()["phase"], Task.Phase.PROPOSAL)
        self.assertEqual(self.task.assigned_to, self.coordinator)
        self.assertTrue(self.task.approved_helpers.filter(pk=self.helper.pk).exists())
        self.assertEqual(TaskVote.objects.filter(task=self.task).count(), 1)

        response = self.cast_support_vote(self.helper)
        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.REALIZATION)
        self.assertEqual(response.json()["phase"], Task.Phase.REALIZATION)

    def test_losing_approved_team_member_returns_to_proposal_and_preserves_votes(self):
        self.task.phase = Task.Phase.REALIZATION
        self.task.save(update_fields=["phase"])
        self.task.approved_helpers.add(self.helper)
        TaskVote.objects.create(task=self.task, user=self.coordinator, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=self.helper, value=TaskVote.Value.UP)
        self.client.force_login(self.coordinator)

        response = self.client.post(reverse("tasks:toggle_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.task.refresh_from_db()
        self.assertEqual(self.task.phase, Task.Phase.PROPOSAL)
        self.assertEqual(response.json()["phase"], Task.Phase.PROPOSAL)
        self.assertEqual(self.task.assigned_to, self.coordinator)
        self.assertFalse(self.task.approved_helpers.exists())
        self.assertEqual(TaskVote.objects.filter(task=self.task).count(), 2)

    def test_phase_migration_reconciles_existing_tasks_without_clearing_votes_or_team(self):
        ready = make_task(title="Ready", assigned_to=self.coordinator, required_people=2)
        ready.approved_helpers.add(self.helper)
        TaskVote.objects.create(task=ready, user=self.coordinator, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=ready, user=self.helper, value=TaskVote.Value.UP)

        no_longer_ready = make_task(title="No longer ready", assigned_to=self.coordinator, phase=Task.Phase.REALIZATION, required_people=2)
        TaskVote.objects.create(task=no_longer_ready, user=self.coordinator, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=no_longer_ready, user=self.helper, value=TaskVote.Value.UP)

        migration = import_module("tasks.migrations.0018_reconcile_task_phases")
        migration.reconcile_active_task_phases(apps, SimpleNamespace(connection=connection))

        ready.refresh_from_db()
        no_longer_ready.refresh_from_db()
        self.assertEqual(ready.phase, Task.Phase.REALIZATION)
        self.assertEqual(no_longer_ready.phase, Task.Phase.PROPOSAL)
        self.assertEqual(no_longer_ready.assigned_to, self.coordinator)
        self.assertEqual(TaskVote.objects.filter(task=no_longer_ready).count(), 2)


class TaskSubtaskViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.coordinator = make_user("subtask-coordinator")
        self.helper = make_user("subtask-helper")
        self.outsider = make_user("subtask-outsider")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, team_mode=True)
        TaskVote.objects.create(task=self.task, user=self.helper, value=TaskVote.Value.UP)
        self.task.approve_helper(self.helper)
        self.subtask = TaskSubtask.objects.create(task=self.task, title="Pierwsze", order=0)

    def test_empty_nested_task_list_is_a_hidden_drag_target(self):
        self.client.force_login(self.coordinator)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertNotContains(response, "Drop a task here to nest it.")
        self.assertNotContains(response, "tw-min-h-8")
        self.assertContains(response, "data-subtask-drop-target")
        self.assertContains(response, "tw-hidden tw-absolute tw-inset-0")

    def test_subtask_name_editing_uses_a_modal_and_renders_nested_items(self):
        child = TaskSubtask.objects.create(task=self.task, parent=self.subtask, title="Dziecko", order=0)
        self.client.force_login(self.helper)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertContains(response, 'id="editSubtaskModal"')
        self.assertContains(response, "data-subtask-edit")
        self.assertContains(response, "data-subtask-delete")
        self.assertNotContains(response, "/indent/")
        self.assertNotContains(response, "/outdent/")
        self.assertNotContains(response, "/move/up/")
        self.assertNotContains(response, "/move/down/")
        self.assertContains(response, f'data-parent-id="{self.subtask.pk}"')
        self.assertContains(response, child.title)
        self.assertNotContains(response, 'id="subtask-title-')

    def test_team_member_can_add_edit_toggle_and_delete_subtask(self):
        self.client.force_login(self.helper)
        self.client.post(reverse("tasks:subtask_add", kwargs={"pk": self.task.pk}), {"title": "Drugie"})
        second = self.task.subtasks.get(title="Drugie")
        self.client.post(reverse("tasks:subtask_edit", kwargs={"pk": self.task.pk, "subtask_pk": second.pk}), {"title": "Zmienione"})
        self.client.post(reverse("tasks:subtask_toggle", kwargs={"pk": self.task.pk, "subtask_pk": second.pk}))
        second.refresh_from_db()
        self.assertEqual(second.title, "Zmienione")
        self.assertTrue(second.is_completed)
        self.client.post(reverse("tasks:subtask_delete", kwargs={"pk": self.task.pk, "subtask_pk": second.pk}))
        self.assertFalse(TaskSubtask.objects.filter(pk=second.pk).exists())

    def test_parent_completion_cascades_and_children_update_parent(self):
        child = TaskSubtask.objects.create(task=self.task, parent=self.subtask, title="Dziecko", order=0)
        self.client.force_login(self.helper)
        self.client.post(reverse("tasks:subtask_toggle", kwargs={"pk": self.task.pk, "subtask_pk": self.subtask.pk}))
        self.subtask.refresh_from_db()
        child.refresh_from_db()
        self.assertTrue(self.subtask.is_completed)
        self.assertTrue(child.is_completed)

        self.client.post(reverse("tasks:subtask_toggle", kwargs={"pk": self.task.pk, "subtask_pk": child.pk}))
        self.subtask.refresh_from_db()
        child.refresh_from_db()
        self.assertFalse(self.subtask.is_completed)
        self.assertFalse(child.is_completed)

    def test_indent_outdent_and_parent_group_reorder(self):
        second = TaskSubtask.objects.create(task=self.task, title="Drugie", order=1)
        self.client.force_login(self.coordinator)

        self.client.post(reverse("tasks:subtask_indent", kwargs={"pk": self.task.pk, "subtask_pk": second.pk}))
        second.refresh_from_db()
        self.assertEqual(second.parent_id, self.subtask.pk)

        self.client.post(reverse("tasks:subtask_outdent", kwargs={"pk": self.task.pk, "subtask_pk": second.pk}))
        second.refresh_from_db()
        self.assertIsNone(second.parent_id)
        self.assertEqual(second.order, 1)
        child = TaskSubtask.objects.create(task=self.task, parent=second, title="Dziecko", order=0)

        url = reverse("tasks:subtask_reorder", kwargs={"pk": self.task.pk})
        response = self.client.post(
            url,
            json.dumps([{"id": second.pk, "parent_id": None, "order": 0}, {"id": child.pk, "parent_id": second.pk, "order": 0}, {"id": self.subtask.pk, "parent_id": None, "order": 1}]),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.subtask.refresh_from_db()
        second.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual((second.order, self.subtask.order), (0, 1))
        self.assertEqual(child.parent_id, second.pk)

    def test_reorder_rejects_nesting_beyond_one_level(self):
        child = TaskSubtask.objects.create(task=self.task, parent=self.subtask, title="Dziecko", order=0)
        grandchild = TaskSubtask.objects.create(task=self.task, title="Wnuk", order=1)
        self.client.force_login(self.coordinator)
        response = self.client.post(
            reverse("tasks:subtask_reorder", kwargs={"pk": self.task.pk}),
            json.dumps([{"id": self.subtask.pk, "parent_id": None, "order": 0}, {"id": child.pk, "parent_id": self.subtask.pk, "order": 0}, {"id": grandchild.pk, "parent_id": child.pk, "order": 0}]),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        grandchild.refresh_from_db()
        self.assertIsNone(grandchild.parent_id)

    def test_parent_with_children_cannot_be_deleted(self):
        child = TaskSubtask.objects.create(task=self.task, parent=self.subtask, title="Dziecko", order=0)
        self.client.force_login(self.coordinator)
        self.client.post(reverse("tasks:subtask_delete", kwargs={"pk": self.task.pk, "subtask_pk": self.subtask.pk}))
        self.assertTrue(TaskSubtask.objects.filter(pk=self.subtask.pk).exists())
        self.assertTrue(TaskSubtask.objects.filter(pk=child.pk).exists())

    def test_unapproved_member_cannot_change_subtasks(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse("tasks:subtask_toggle", kwargs={"pk": self.task.pk, "subtask_pk": self.subtask.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)
        self.subtask.refresh_from_db()
        self.assertFalse(self.subtask.is_completed)

    def test_closed_task_locks_subtasks(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save(update_fields=["status"])
        self.client.force_login(self.coordinator)
        self.client.post(reverse("tasks:subtask_toggle", kwargs={"pk": self.task.pk, "subtask_pk": self.subtask.pk}))
        self.subtask.refresh_from_db()
        self.assertFalse(self.subtask.is_completed)

    def test_keyboard_move_changes_subtask_order(self):
        second = TaskSubtask.objects.create(task=self.task, title="Drugie", order=1)
        self.client.force_login(self.coordinator)
        self.client.post(reverse("tasks:subtask_move", kwargs={"pk": self.task.pk, "subtask_pk": second.pk, "direction": "up"}))
        self.subtask.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((second.order, self.subtask.order), (0, 1))

    def test_reorder_requires_exact_task_subtask_ids(self):
        second = TaskSubtask.objects.create(task=self.task, title="Drugie", order=1)
        self.client.force_login(self.coordinator)
        url = reverse("tasks:subtask_reorder", kwargs={"pk": self.task.pk})
        response = self.client.post(url, json.dumps([{"id": second.pk, "parent_id": None, "order": 0}, {"id": self.subtask.pk, "parent_id": None, "order": 1}]), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.subtask.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((second.order, self.subtask.order), (0, 1))
        response = self.client.post(url, json.dumps([{"id": second.pk, "order": 0}]), content_type="application/json")
        self.assertEqual(response.status_code, 400)


class CoordinatorRankingTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.coordinator_a = make_user("ranking-a")
        self.coordinator_b = make_user("ranking-b")
        self.coordinator_c = make_user("ranking-c")
        self.client.force_login(self.coordinator_a)

    def test_ranking_rewards_successful_outcomes_for_each_terminal_status(self):
        completed_a = make_task(status=Task.Status.COMPLETED, assigned_to=self.coordinator_a)
        cancelled_a = make_task(status=Task.Status.CANCELLED, assigned_to=self.coordinator_a)
        completed_b = make_task(status=Task.Status.COMPLETED, assigned_to=self.coordinator_b)
        cancelled_b1 = make_task(status=Task.Status.CANCELLED, assigned_to=self.coordinator_b)
        make_task(status=Task.Status.CANCELLED, assigned_to=self.coordinator_b)
        rejected = make_task(status=Task.Status.REJECTED, assigned_to=self.coordinator_b)
        unassigned = make_task(status=Task.Status.COMPLETED)
        completed_c = make_task(status=Task.Status.COMPLETED, assigned_to=self.coordinator_c)
        make_task(status=Task.Status.CANCELLED, assigned_to=self.coordinator_c)
        make_task(status=Task.Status.CANCELLED, assigned_to=self.coordinator_c)

        TaskEvaluation.objects.create(task=completed_a, user=self.coordinator_a, value=TaskEvaluation.Value.SUCCESS)
        TaskEvaluation.objects.create(task=completed_a, user=self.coordinator_b, value=TaskEvaluation.Value.SUCCESS)
        TaskEvaluation.objects.create(task=cancelled_a, user=self.coordinator_a, value=TaskEvaluation.Value.SUCCESS)
        TaskEvaluation.objects.create(task=cancelled_a, user=self.coordinator_b, value=TaskEvaluation.Value.FAILURE)
        TaskEvaluation.objects.create(task=completed_b, user=self.coordinator_a, value=TaskEvaluation.Value.SUCCESS)
        TaskEvaluation.objects.create(task=cancelled_b1, user=self.coordinator_a, value=TaskEvaluation.Value.FAILURE)
        TaskEvaluation.objects.create(task=rejected, user=self.coordinator_a, value=TaskEvaluation.Value.SUCCESS)
        TaskEvaluation.objects.create(task=unassigned, user=self.coordinator_a, value=TaskEvaluation.Value.SUCCESS)
        TaskEvaluation.objects.create(task=completed_c, user=self.coordinator_a, value=TaskEvaluation.Value.SUCCESS)

        response = self.client.get(reverse("tasks:stats"))
        ranking = response.context["coordinator_ranking"]
        self.assertEqual([row["coordinator"] for row in ranking], [self.coordinator_b, self.coordinator_c, self.coordinator_a])
        self.assertEqual(ranking[0]["successful_outcomes"], 2)
        self.assertEqual(ranking[0]["total_closed"], 4)
        self.assertEqual(ranking[0]["outcomes"][Task.Status.REJECTED]["success"], 1)
        self.assertEqual(ranking[0]["outcomes"][Task.Status.CANCELLED]["failure"], 1)
        self.assertEqual(ranking[0]["outcomes"][Task.Status.CANCELLED]["no_evaluations"], 1)
        self.assertEqual(ranking[2]["outcomes"][Task.Status.CANCELLED]["mixed"], 1)
        self.assertEqual(ranking[2]["successful_outcomes"], 1)


class EvaluateTaskTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("evaluator")
        self.task = make_task(status=Task.Status.COMPLETED)

    def test_evaluate_success(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:evaluate", kwargs={"pk": self.task.pk}), {"value": "success"})
        self.assertTrue(TaskEvaluation.objects.filter(task=self.task, user=self.user, value="success").exists())

    def test_evaluate_failure(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:evaluate", kwargs={"pk": self.task.pk}), {"value": "failure"})
        self.assertTrue(TaskEvaluation.objects.filter(task=self.task, user=self.user, value="failure").exists())

    def test_same_evaluation_twice_removes_it(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:evaluate", kwargs={"pk": self.task.pk}), {"value": "success"})
        self.client.post(reverse("tasks:evaluate", kwargs={"pk": self.task.pk}), {"value": "success"})
        self.assertFalse(TaskEvaluation.objects.filter(task=self.task, user=self.user).exists())

    def test_flip_evaluation_success_to_failure(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:evaluate", kwargs={"pk": self.task.pk}), {"value": "success"})
        self.client.post(reverse("tasks:evaluate", kwargs={"pk": self.task.pk}), {"value": "failure"})
        ev = TaskEvaluation.objects.get(task=self.task, user=self.user)
        self.assertEqual(ev.value, TaskEvaluation.Value.FAILURE)

    def test_invalid_evaluation_value_ignored(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:evaluate", kwargs={"pk": self.task.pk}), {"value": "invalid"})
        self.assertFalse(TaskEvaluation.objects.filter(task=self.task, user=self.user).exists())


class CategoryAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("catuser")
        self.cat = Category.objects.create(slug="test-cat", name="Test", description="Desc", order=10)

    def test_list_requires_login(self):
        response = self.client.get(reverse("tasks:api_categories"))
        self.assertEqual(response.status_code, 302)

    def test_list_returns_categories(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:api_categories"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        slugs = [c["slug"] for c in data["categories"]]
        self.assertIn("test-cat", slugs)

    def test_create_category(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_categories"), {"name": "Nowa", "description": "Opis"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(name="Nowa").exists())

    def test_create_category_empty_name_returns_400(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_categories"), {"name": "", "description": ""})
        self.assertEqual(response.status_code, 400)

    def test_create_category_unslugifiable_name_returns_400(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_categories"), {"name": "!!!", "description": ""})
        self.assertEqual(response.status_code, 400)

    def test_create_category_duplicate_name_gets_unique_slug(self):
        Category.objects.create(name="Nowa", slug="nowa")
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_categories"), {"name": "Nowa", "description": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], "nowa-1")
        self.assertTrue(Category.objects.filter(slug="nowa-1").exists())

    def test_edit_category_get_returns_categories(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:api_categories"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(item["id"] == self.cat.pk for item in response.json()["categories"]))

    def test_edit_category_requires_login(self):
        url = reverse("tasks:api_category_edit", kwargs={"pk": self.cat.pk})

        self.assertEqual(self.client.get(url).status_code, 302)
        response = self.client.post(url, {"name": "Updated", "description": ""})

        self.assertEqual(response.status_code, 302)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.name, "Test")

    def test_authenticated_edit_category_api_rejects_get(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("tasks:api_category_edit", kwargs={"pk": self.cat.pk}))

        self.assertEqual(response.status_code, 405)

    def test_edit_category_requires_csrf_when_checks_are_enabled(self):
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(reverse("tasks:api_category_edit", kwargs={"pk": self.cat.pk}), {"name": "Updated", "description": ""})

        self.assertEqual(response.status_code, 403)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.name, "Test")

    def test_edit_category(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_category_edit", kwargs={"pk": self.cat.pk}), {"name": "Zmieniona", "description": "Nowy opis"})
        self.assertEqual(response.status_code, 200)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.name, "Zmieniona")

    def test_edit_category_empty_name_returns_400(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_category_edit", kwargs={"pk": self.cat.pk}), {"name": "", "description": ""})
        self.assertEqual(response.status_code, 400)

    def test_delete_category(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_category_delete", kwargs={"pk": self.cat.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Category.objects.filter(pk=self.cat.pk).exists())

    def test_delete_protected_category_returns_403(self):
        protected = Category.objects.create(slug="locked", name="Locked", is_protected=True)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:api_category_delete", kwargs={"pk": protected.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Category.objects.filter(pk=protected.pk).exists())

    def test_delete_sets_task_category_to_null(self):
        task = make_task(created_by=self.user)
        task.category = self.cat
        task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:api_category_delete", kwargs={"pk": self.cat.pk}))
        task.refresh_from_db()
        self.assertIsNone(task.category)


class TaskAgainstJsonTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("requester")
        self.task = make_task(created_by=self.user)

    def test_requires_login(self):
        response = self.client.get(reverse("tasks:against_json", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 302)

    def test_returns_only_down_voters(self):
        helper = make_user("helper")
        opponent = make_user("opponent")
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=opponent, value=TaskVote.Value.DOWN)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:against_json", kwargs={"pk": self.task.pk}))
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["helpers"]), 1)
        self.assertEqual(data["helpers"][0]["username"], "opponent")

    def test_returns_empty_when_no_down_votes(self):
        helper = make_user("helper")
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.UP)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:against_json", kwargs={"pk": self.task.pk}))
        data = response.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["helpers"], [])


class TaskCreateTeamModeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("creator")

    def test_create_sets_team_mode_true(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), task_form_data(title="Nowe", description="Opis"))
        task = Task.objects.get(title="Nowe")
        self.assertTrue(task.team_mode)

    def test_create_assigns_creator_as_coordinator(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), task_form_data(title="Kierowane", description="Opis"))
        task = Task.objects.get(title="Kierowane")
        self.assertEqual(task.assigned_to, self.user)


class HelperApprovalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.coordinator = make_user("coordinator")
        self.helper = make_user("helper")
        self.intruder = make_user("intruder")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, team_mode=True)
        TaskVote.objects.create(task=self.task, user=self.helper, value=TaskVote.Value.UP)

    def test_coordinator_approves_helper(self):
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:approve_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(self.task.is_user_approved(self.helper))

    def test_non_coordinator_cannot_approve(self):
        self.client.login(username=self.intruder.username, password=self.intruder._plain_password)
        response = self.client.post(reverse("tasks:approve_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.task.is_user_approved(self.helper))

    def test_coordinator_removes_helper_from_team_keeps_vote(self):
        self.task.approve_helper(self.helper)
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:remove_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(self.task.is_user_approved(self.helper))
        self.assertTrue(self.task.is_user_helper(self.helper))

    def test_approve_non_helper_fails(self):
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:approve_helper", kwargs={"pk": self.task.pk, "user_id": self.intruder.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.task.is_user_approved(self.intruder))

    def test_coordinator_cannot_approve_self(self):
        TaskVote.objects.create(task=self.task, user=self.coordinator, value=TaskVote.Value.UP)
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:approve_helper", kwargs={"pk": self.task.pk, "user_id": self.coordinator.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.task.is_user_approved(self.coordinator))

    def test_coordinator_cannot_remove_self(self):
        TaskVote.objects.create(task=self.task, user=self.coordinator, value=TaskVote.Value.UP)
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:remove_helper", kwargs={"pk": self.task.pk, "user_id": self.coordinator.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.task.is_user_approved(self.coordinator))


class TaskDetailTeamModeContextTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.coordinator = make_user("coordinator")
        self.helper = make_user("helper")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, team_mode=True)
        TaskVote.objects.create(task=self.task, user=self.helper, value=TaskVote.Value.UP)

    def test_detail_context_includes_is_coordinator(self):
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_coordinator"])

    def test_detail_context_can_post_coordinator(self):
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_post_in_chat"])

    def test_detail_context_can_post_unapproved_helper_false(self):
        self.client.login(username=self.helper.username, password=self.helper._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_post_in_chat"])
        self.assertContains(response, 'data-can-post="false"')
        self.assertContains(response, 'data-source-app="tasks"')

    def test_detail_context_can_post_approved_helper_true(self):
        self.task.approve_helper(self.helper)
        self.client.login(username=self.helper.username, password=self.helper._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_post_in_chat"])

    def test_detail_context_coordinator_is_first_and_approved(self):
        helper2 = make_user("helper2")
        TaskVote.objects.create(task=self.task, user=helper2, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=self.coordinator, value=TaskVote.Value.UP)
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": self.task.pk}))
        self.assertEqual(response.status_code, 200)
        votes = response.context["helping_votes"]
        self.assertTrue(votes[0].is_coordinator)
        self.assertEqual(votes[0].user_id, self.coordinator.id)
        self.assertTrue(votes[0].is_approved)


class HelperToggleTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.coordinator = make_user("coordinator")
        self.helper = make_user("helper")
        self.intruder = make_user("intruder")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, team_mode=True)
        TaskVote.objects.create(task=self.task, user=self.helper, value=TaskVote.Value.UP)

    def test_coordinator_toggle_approves_helper(self):
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:toggle_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["approved"])
        self.assertTrue(self.task.is_user_approved(self.helper))

    def test_coordinator_toggle_removes_helper(self):
        self.task.approve_helper(self.helper)
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:toggle_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["approved"])
        self.assertFalse(self.task.is_user_approved(self.helper))

    def test_non_coordinator_cannot_toggle(self):
        self.client.login(username=self.intruder.username, password=self.intruder._plain_password)
        response = self.client.post(reverse("tasks:toggle_helper", kwargs={"pk": self.task.pk, "user_id": self.helper.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)

    def test_toggle_non_helper_fails(self):
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:toggle_helper", kwargs={"pk": self.task.pk, "user_id": self.intruder.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)

    def test_coordinator_cannot_toggle_self(self):
        TaskVote.objects.create(task=self.task, user=self.coordinator, value=TaskVote.Value.UP)
        self.client.login(username=self.coordinator.username, password=self.coordinator._plain_password)
        response = self.client.post(reverse("tasks:toggle_helper", kwargs={"pk": self.task.pk, "user_id": self.coordinator.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.task.is_user_approved(self.coordinator))
