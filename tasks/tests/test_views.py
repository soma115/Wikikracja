# Third party imports
from django.test import Client, TestCase
from django.urls import reverse

# Local folder imports
from tasks.models import Category, Task, TaskEvaluation, TaskVote
from tasks.tests.utils import make_task, make_user


class TaskListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("listuser")

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
        active = make_task(title="W realizacji", assigned_to=self.other)
        self.upvote(active, self.user)
        self.upvote(active, self.other)
        response = self.get_list("?tab=awaiting")
        titles = [t.title for t in response.context["awaiting_tasks"]]
        self.assertIn("Oczekujące", titles)
        self.assertNotIn("W realizacji", titles)

    def test_active_tab_requires_coordinator_and_score_2(self):
        no_owner = make_task(title="Bez koordynatora")
        owned = make_task(title="Z koordynatorem", assigned_to=self.other)
        self.upvote(no_owner, self.user)
        self.upvote(no_owner, self.other)
        self.upvote(owned, self.user)
        self.upvote(owned, self.other)
        response = self.get_list("?tab=active")
        titles = [t.title for t in response.context["active_tasks"]]
        self.assertIn("Z koordynatorem", titles)
        # score>=2 ale bez koordynatora → nadal oczekujące
        self.assertNotIn("Bez koordynatora", titles)

    def test_finished_tab_collects_all_rejected(self):
        rejected = make_task(title="Odrzucone")
        self.upvote(rejected, self.user, TaskVote.Value.DOWN)
        self.upvote(rejected, self.other, TaskVote.Value.DOWN)
        response = self.get_list("?tab=finished")
        titles = [t.title for t in response.context["finished_rejected"]]
        self.assertIn("Odrzucone", titles)
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

    def test_post_creates_task(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), {"title": "Nowe zadanie", "description": "Opis"})
        self.assertTrue(Task.objects.filter(title="Nowe zadanie").exists())

    def test_post_assigns_creator_as_created_by_and_assigned_to(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), {"title": "Moje zadanie", "description": "Opis"})
        task = Task.objects.get(title="Moje zadanie")
        self.assertEqual(task.created_by, self.user)
        self.assertEqual(task.assigned_to, self.user)

    def test_post_creates_upvote_for_creator(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), {"title": "Auto-vote", "description": "Opis"})
        task = Task.objects.get(title="Auto-vote")
        vote = TaskVote.objects.filter(task=task, user=self.user).first()
        self.assertIsNotNone(vote)
        self.assertEqual(vote.value, TaskVote.Value.UP)

    def test_post_empty_title_returns_form(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:add"), {"title": "", "description": "Opis"})
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

    def test_nonexistent_task_returns_404(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.get(reverse("tasks:detail", kwargs={"pk": 99999}))
        self.assertEqual(response.status_code, 404)


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
        response = self.client.get(reverse("tasks:edit", kwargs={"pk": self.task.pk}))
        self.assertRedirects(response, reverse("tasks:detail", kwargs={"pk": self.task.pk}))

    def test_edit_updates_title(self):
        self.client.login(username=self.owner.username, password=self.owner._plain_password)
        self.client.post(reverse("tasks:edit", kwargs={"pk": self.task.pk}), {"title": "Zmieniony tytuł", "description": "Nowy opis"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Zmieniony tytuł")


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

    def test_resign_does_not_promote_approved_helper(self):
        # Sukcesja jest wyłączona — zadanie wraca do puli nawet gdy zespół nie jest pusty.
        helper = make_user("helper")
        TaskVote.objects.create(task=self.task, user=helper, value=TaskVote.Value.UP)
        self.task.approved_helpers.add(helper)
        self.task.assigned_to = self.user
        self.task.save()
        self.client.login(username=self.user.username, password=self.user._plain_password)
        response = self.client.post(reverse("tasks:resign", kwargs={"pk": self.task.pk}), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_to)
        self.assertIsNone(response.json()["assigned_to"])
        self.assertFalse(response.json()["in_team"])
        self.assertTrue(self.task.approved_helpers.filter(pk=helper.pk).exists())

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
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": 1})
        vote = TaskVote.objects.get(task=self.task, user=self.user)
        self.assertEqual(vote.value, TaskVote.Value.UP)

    def test_score_minus_2_rejects_task(self):
        user2 = make_user("voter2")
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.client.logout()
        self.client.login(username=user2.username, password=user2._plain_password)
        self.client.post(reverse("tasks:vote", kwargs={"pk": self.task.pk}), {"value": -1})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.REJECTED)

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

    def test_reopen_already_active_task_does_nothing(self):
        active_task = make_task(created_by=self.user, status=Task.Status.ACTIVE)
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:reopen", kwargs={"pk": active_task.pk}))
        active_task.refresh_from_db()
        self.assertEqual(active_task.status, Task.Status.ACTIVE)

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
        self.client.post(reverse("tasks:add"), {"title": "Nowe", "description": "Opis"})
        task = Task.objects.get(title="Nowe")
        self.assertTrue(task.team_mode)

    def test_create_assigns_creator_as_coordinator(self):
        self.client.login(username=self.user.username, password=self.user._plain_password)
        self.client.post(reverse("tasks:add"), {"title": "Kierowane", "description": "Opis"})
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
