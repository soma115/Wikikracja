"""
Testy widoku set_user_language: wybór języka musi działać dla NIEzalogowanych
(strona startowa + cały proces zakładania konta), z trwałością przez cookie
`django_language`, a dla zalogowanych dodatkowo zapisywać się do profilu.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import override, pgettext

from chat.models import Message, Room
from chat.services import get_user_public_message_rows
from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
from obywatele.auth_backends import CaseInsensitiveEmailBackend
from obywatele.models import CitizenActivity, Rate, Uzytkownik
from obywatele.services import get_citizen_activity, get_citizen_created_items
from tasks.activity import get_user_tasks
from tasks.models import Task, TaskEvaluation, TaskVote
from tests.factories import DecyzjaFactory, RoomFactory

PROFILE_POST_DATA = {
    'first_name': 'Jan',
    'last_name': 'Kowalski',
    'phone': '123456789',
    'city': 'Gdańsk',
    'job': 'Programista',
    'responsibilities': '',
    'voivodeship': '',
    'skills_knowledge_hobby': 'Python',
    'to_give_away': 'Rower',
    'to_borrow': 'Wiertarka',
    'for_sale': 'Kanapa',
    'i_need': 'Pomoc',
    'want_to_learn': 'Go',
    'business': 'IT',
    'why': 'Chcę pomagać',
}


class DebugSkipAuthTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='debug-auth', email='debug@example.com', password='correct-password')
        self.backend = CaseInsensitiveEmailBackend()

    @override_settings(DEBUG=False, DEBUG_SKIP_AUTH=True)
    def test_skip_auth_is_ignored_outside_debug_mode(self):
        authenticated = self.backend.authenticate(None, username=self.user.email, password='wrong-password')

        self.assertIsNone(authenticated)

    @override_settings(DEBUG=True, DEBUG_SKIP_AUTH=True)
    def test_skip_auth_still_works_in_debug_mode(self):
        authenticated = self.backend.authenticate(None, username=self.user.email, password='wrong-password')

        self.assertEqual(authenticated, self.user)


class SetLanguageAnonymousTest(TestCase):
    """Niezalogowany użytkownik może wybrać język — utrwalony w cookie."""

    def setUp(self):
        self.url = reverse('obywatele:set_language')
        self.cookie_name = settings.LANGUAGE_COOKIE_NAME

    def test_anonymous_can_set_language_sets_cookie(self):
        response = self.client.post(self.url, {'language': 'en', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        self.assertIn(self.cookie_name, response.cookies)
        self.assertEqual(response.cookies[self.cookie_name].value, 'en')

    def test_anonymous_invalid_language_ignored(self):
        response = self.client.post(self.url, {'language': 'xx', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        # Nieobsługiwany kod języka w ogóle nie dotyka cookie (gałąź else widoku)
        self.assertNotIn(self.cookie_name, response.cookies)

    def test_external_next_is_rejected(self):
        """Otwarty endpoint nie może być wektorem open-redirect."""
        response = self.client.post(self.url, {'language': 'en', 'next': 'https://evil.example/'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')


class SetLanguageAuthenticatedTest(TestCase):
    """Zalogowany użytkownik: wybór zapisuje się do profilu ORAZ do cookie."""

    def setUp(self):
        self.url = reverse('obywatele:set_language')
        self.cookie_name = settings.LANGUAGE_COOKIE_NAME
        self.user = User.objects.create_user(username='lang', password='secret', is_active=True)
        self.client.force_login(self.user)

    def test_authenticated_persists_to_profile_and_cookie(self):
        response = self.client.post(self.url, {'language': 'en', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        self.user.uzytkownik.refresh_from_db()
        self.assertEqual(self.user.uzytkownik.language, 'en')
        self.assertEqual(response.cookies[self.cookie_name].value, 'en')

    def test_authenticated_auto_resets_profile_and_deletes_cookie(self):
        # najpierw ustaw konkretny język
        self.client.post(self.url, {'language': 'en', 'next': '/'})
        # potem "Auto (browser)" = pusty język
        response = self.client.post(self.url, {'language': '', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        self.user.uzytkownik.refresh_from_db()
        self.assertEqual(self.user.uzytkownik.language, '')
        # "Auto" usuwa cookie języka — wygaszenie sygnalizowane przez max-age=0
        self.assertIn(self.cookie_name, response.cookies)
        self.assertEqual(response.cookies[self.cookie_name]['max-age'], 0)


class LanguageSwitcherRenderTest(TestCase):
    """Przełącznik języka jest widoczny przez CAŁY anonimowy flow zakładania konta.

    Wszystkie te strony rozszerzają home/base.html i biegną dla niezalogowanego
    użytkownika, więc dzielą anon-topbar ze switcherem. Asercja na każdym kroku
    pilnuje właściwego wymogu: gdyby ktoś przeniósł switcher poza anon-topbar albo
    dał @login_required na onboarding, te testy to złapią.
    """

    def setUp(self):
        self.switcher_url = reverse('obywatele:set_language')

    def test_home_anonymous_renders_language_switcher(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.switcher_url)

    def test_signup_renders_language_switcher(self):
        response = self.client.get(reverse('account_signup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.switcher_url)

    def test_onboarding_renders_language_switcher(self):
        # Onboarding biegnie bez @login_required — dostęp z onboarding_user_id w sesji.
        user = User.objects.create_user(username='onb', email='onb@example.com', password='secret', is_active=False)
        session = self.client.session
        session['onboarding_user_id'] = user.id
        session.save()

        response = self.client.get(reverse('obywatele:onboarding_details'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.switcher_url)


class CitizenZalozonoTemplateTest(TestCase):
    """Widok citizen_zalozono musi renderować inny szablon dla żądań AJAX i zwykłych."""

    def setUp(self):
        self.user = User.objects.create_user(username='zalozono', password='secret', is_active=True)
        self.url = reverse('obywatele:citizen_zalozono', kwargs={'pk': self.user.pk})

    def test_non_ajax_renders_full_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'obywatele/citizen_zalozono.html')

    def test_ajax_renders_partial_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'obywatele/_citizen_zalozono_partial.html')


@override_settings(LANGUAGE_CODE='en')
class CitizenTabContentTest(TestCase):
    def setUp(self):
        self.enterContext(patch('core.notifications._dispatch_notification'))
        self.enterContext(override('en'))
        self.user = User.objects.create_user(username='citizen', password='secret', is_active=True)
        self.other = User.objects.create_user(username='viewer', password='secret', is_active=True)
        CitizenActivity.objects.filter(uzytkownik__uid__in=(self.user, self.other)).delete()
        self.client.force_login(self.other)
        self.start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def get_tab(self, tab):
        response = self.client.get(reverse(f'obywatele:citizen_{tab}', kwargs={'pk': self.user.pk}), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['target_user'], self.user)
        self.assertFalse(response.context['is_own'])
        return response

    def test_empty_tabs_preserve_urls_templates_context_and_ownership(self):
        for viewer in (self.user, self.other):
            self.client.force_login(viewer)
            for tab, context_key in (('aktywnosc', 'items'), ('zalozono', 'items'), ('zadania', 'tasks'), ('czaty', 'rows')):
                url = reverse(f'obywatele:citizen_{tab}', kwargs={'pk': self.user.pk})
                self.assertTrue(url.endswith(f'/{self.user.pk}/{tab}/'))
                for ajax in (False, True):
                    with self.subTest(viewer=viewer.username, tab=tab, ajax=ajax):
                        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
                        response = self.client.get(url, **headers)
                        template = f'obywatele/_citizen_{tab}_partial.html' if ajax else f'obywatele/citizen_{tab}.html'
                        self.assertEqual(response.status_code, 200)
                        self.assertTemplateUsed(response, template)
                        self.assertEqual(response.context['target_user'], self.user)
                        self.assertEqual(response.context['is_own'], viewer == self.user)
                        self.assertEqual(list(response.context[context_key]), [])

    def test_aktywnosc_filters_all_sources_and_sorts_dated_items_before_signatures(self):
        task = Task.objects.create(title='Created and assigned', created_by=self.user, assigned_to=self.user)
        other_task = Task.objects.create(title='Voted and evaluated', created_by=self.other, assigned_to=self.other)
        vote = TaskVote.objects.create(task=other_task, user=self.user, value=TaskVote.Value.UP)
        evaluation = TaskEvaluation.objects.create(task=other_task, user=self.user, value=TaskEvaluation.Value.SUCCESS)
        TaskVote.objects.create(task=other_task, user=self.other, value=TaskVote.Value.DOWN)
        TaskEvaluation.objects.create(task=other_task, user=self.other, value=TaskEvaluation.Value.FAILURE)
        proposal = DecyzjaFactory(author=self.other)
        other_proposal = DecyzjaFactory(author=self.other)
        argument = Argument.objects.create(decyzja=proposal, author=self.user, argument_type='FOR', content='Target argument')
        Argument.objects.create(decyzja=other_proposal, author=self.other, argument_type='AGAINST', content='Other argument')
        ZebranePodpisy.objects.create(projekt=proposal, podpis_uzytkownika=self.user)
        ZebranePodpisy.objects.create(projekt=None, podpis_uzytkownika=self.user)
        ZebranePodpisy.objects.create(projekt=other_proposal, podpis_uzytkownika=self.other)
        event = CitizenActivity.objects.create(uzytkownik=self.user.uzytkownik, activity_type=CitizenActivity.ActivityType.USER_ACTIVATED)
        CitizenActivity.objects.create(uzytkownik=self.other.uzytkownik, activity_type=CitizenActivity.ActivityType.USER_BLOCKED)
        times = [self.start + timedelta(days=day) for day in range(6)]
        Task.objects.filter(pk=task.pk).update(created_at=times[0], updated_at=times[4])
        TaskVote.objects.filter(pk=vote.pk).update(updated_at=times[2])
        TaskEvaluation.objects.filter(pk=evaluation.pk).update(updated_at=times[1])
        Argument.objects.filter(pk=argument.pk).update(created_at=times[5])
        CitizenActivity.objects.filter(pk=event.pk).update(timestamp=times[3])
        task_url = reverse('tasks:detail', kwargs={'pk': task.pk})
        other_task_url = reverse('tasks:detail', kwargs={'pk': other_task.pk})
        proposal_url = reverse('glosowania:details', kwargs={'pk': proposal.pk})

        response = self.get_tab('aktywnosc')

        expected = [
            ('argument', proposal.title, times[5], _('Added argument'), proposal_url),
            ('task_assigned', task.title, times[4], _('Assigned activity'), task_url),
            ('citizen', event.get_activity_type_display(), times[3], _('Citizenship event'), None),
            ('task_vote', other_task.title, times[2], _('Voted on activity'), other_task_url),
            ('task_eval', other_task.title, times[1], _('Evaluated activity'), other_task_url),
            ('task_created', task.title, times[0], _('Created activity'), task_url),
            ('signature', proposal.title, None, _('Signed proposal'), proposal_url),
        ]
        self.assertEqual(response.context['items'], [dict(zip(('type', 'title', 'ts', 'label', 'url'), row, strict=True)) for row in expected])
        self.assertContains(response, proposal_url)
        self.assertNotContains(response, other_proposal.title)

    def test_aktywnosc_reveals_referendum_participation_without_choice_or_code(self):
        proposal = DecyzjaFactory(author=self.other, status=Decyzja.Status.REFERENDUM)
        other_proposal = DecyzjaFactory(author=self.other, status=Decyzja.Status.REFERENDUM)
        KtoJuzGlosowal.objects.create(projekt=proposal, ktory_uzytkownik_juz_zaglosowal=self.user)
        KtoJuzGlosowal.objects.create(projekt=other_proposal, ktory_uzytkownik_juz_zaglosowal=self.other)
        code = VoteCode.objects.create(project=proposal, code='private-ballot-code', vote=True)
        url = reverse('glosowania:details', kwargs={'pk': proposal.pk})
        expected = [{'type': 'voted', 'title': proposal.title, 'ts': None, 'label': _('Voted in referendum'), 'url': url}]

        response = self.get_tab('aktywnosc')

        self.assertEqual(response.context['items'], expected)
        self.assertContains(response, proposal.title)
        self.assertContains(response, url)
        self.assertNotContains(response, code.code)
        self.assertNotContains(response, other_proposal.title)
        VoteCode.objects.filter(pk=code.pk).update(vote=False, code='changed-ballot-code')
        changed_response = self.get_tab('aktywnosc')
        self.assertEqual(changed_response.context['items'], expected)
        self.assertEqual(changed_response.content, response.content)

    def test_zadania_includes_creator_or_assignee_once_but_not_votes_or_evaluations(self):
        created = Task.objects.create(title='Created only', created_by=self.user, assigned_to=self.other)
        assigned = Task.objects.create(title='Assigned only', created_by=self.other, assigned_to=self.user, status=Task.Status.COMPLETED)
        both = Task.objects.create(title='Both roles', created_by=self.user, assigned_to=self.user)
        unrelated = Task.objects.create(title='Only voted and evaluated', created_by=self.other, assigned_to=self.other)
        TaskVote.objects.create(task=unrelated, user=self.user, value=TaskVote.Value.UP)
        TaskEvaluation.objects.create(task=unrelated, user=self.user, value=TaskEvaluation.Value.SUCCESS)
        for day, task in enumerate((assigned, both, created)):
            Task.objects.filter(pk=task.pk).update(created_at=self.start + timedelta(days=day), updated_at=self.start - timedelta(days=day))

        response = self.get_tab('zadania')

        self.assertEqual(list(response.context['tasks']), [created, both, assigned])
        for task in (created, both, assigned):
            self.assertContains(response, task.title)
            self.assertContains(response, reverse('tasks:detail', kwargs={'pk': task.pk}))
        self.assertNotContains(response, unrelated.title)

    def test_zalozono_filters_founders_and_includes_generated_public_rooms(self):
        task = Task.objects.create(title='Founded activity', created_by=self.user)
        Task.objects.create(title='Assigned not founded', created_by=self.other, assigned_to=self.user)
        proposal = DecyzjaFactory(author=self.user)
        DecyzjaFactory(author=self.other)
        undated = DecyzjaFactory(author=self.user, title=None, status=Decyzja.Status.APPROVED)
        public = RoomFactory(title='Founded public room', founder=self.user, archived=True)
        private = RoomFactory(title='Founded private room', founder=self.user, public=False)
        RoomFactory(title='Other public room', founder=self.other)
        RoomFactory(title='No founder', founder=None)
        private.allowed.add(self.user, self.other)
        times = [self.start + timedelta(days=day) for day in range(5)]
        Task.objects.filter(pk=task.pk).update(created_at=times[2])
        Decyzja.objects.filter(pk=proposal.pk).update(data_powstania=times[1].date())
        Decyzja.objects.filter(pk=undated.pk).update(data_powstania=None)
        for room, timestamp in ((public, times[4]), (task.chat_room, times[0]), (proposal.chat_room, times[3])):
            Room.objects.filter(pk=room.pk).update(last_activity=timestamp)
        chat_url = reverse('chat:chat')

        response = self.get_tab('zalozono')

        expected = [
            (public.displayed_name(self.user), times[4], _('Chat room'), f'{chat_url}#room_id={public.pk}'),
            (proposal.chat_room.displayed_name(self.user), times[3], _('Chat room'), f'{chat_url}#room_id={proposal.chat_room_id}'),
            (task.title, times[2], pgettext('task', 'Activity'), reverse('tasks:detail', kwargs={'pk': task.pk})),
            (proposal.title, times[1], _('Voting proposal'), reverse('glosowania:details', kwargs={'pk': proposal.pk})),
            (task.chat_room.displayed_name(self.user), times[0], _('Chat room'), f'{chat_url}#room_id={task.chat_room_id}'),
            ('—', None, _('Voting proposal'), reverse('glosowania:details', kwargs={'pk': undated.pk})),
        ]
        self.assertEqual(response.context['items'], [dict(zip(('title', 'ts', 'label', 'url'), row, strict=True)) for row in expected])
        self.assertContains(response, f'{chat_url}#room_id={public.pk}')
        self.assertNotContains(response, private.title)

    def test_czaty_does_not_attribute_anonymous_messages_to_citizen(self):
        room = RoomFactory(title='Anonymous public conversation')
        message = Message.objects.create(room=room, sender=self.user, anonymous=True, text='Anonymous message secret')
        url = reverse('obywatele:citizen_czaty', kwargs={'pk': self.user.pk})

        for viewer in (self.other, self.user):
            self.client.force_login(viewer)
            for ajax in (False, True):
                with self.subTest(viewer=viewer.username, ajax=ajax):
                    headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
                    response = self.client.get(url, **headers)

                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn(message.pk, [row['msg'].pk for row in response.context['rows']])
                    self.assertNotContains(response, message.text)

    def test_czaty_filters_sender_and_private_rooms_and_orders_messages_newest_first(self):
        public = RoomFactory(title='Public conversation', founder=self.other)
        archived = RoomFactory(title='Archived conversation', founder=self.user, archived=True)
        private = RoomFactory(title='Private conversation', founder=self.user, public=False)
        private.allowed.add(self.user, self.other)
        newest = Message.objects.create(room=public, sender=self.user, text='Newest public message')
        oldest = Message.objects.create(room=public, sender=self.user, text='Oldest public message')
        middle = Message.objects.create(room=archived, sender=self.user, text='Archived public message')
        Message.objects.create(room=public, sender=self.other, text='Other sender message')
        Message.objects.create(room=public, sender=None, anonymous=True, text='Unattributed message')
        Message.objects.create(room=private, sender=self.user, text='Private message secret')
        Room.objects.filter(pk=archived.pk).update(archived=True)
        for day, message in enumerate((oldest, middle, newest)):
            Message.objects.filter(pk=message.pk).update(time=self.start + timedelta(days=day))

        response = self.get_tab('czaty')

        expected = [{'room': message.room, 'room_name': message.room.displayed_name(self.other), 'msg': message} for message in (newest, middle, oldest)]
        self.assertEqual(response.context['rows'], expected)
        for message in (newest, middle, oldest):
            self.assertContains(response, message.text)
            self.assertContains(response, f'{reverse("chat:chat")}#room_id={message.room_id}&message_id={message.pk}')
        for text in ('Other sender message', 'Unattributed message', 'Private message secret', private.title):
            self.assertNotContains(response, text)

    def create_activity_sources(self):
        task = Task.objects.create(title='Citizen activity', created_by=self.user, assigned_to=self.user)
        TaskVote.objects.create(task=task, user=self.user, value=TaskVote.Value.UP)
        TaskEvaluation.objects.create(task=task, user=self.user, value=TaskEvaluation.Value.SUCCESS)
        proposal = DecyzjaFactory(author=self.user)
        Argument.objects.create(decyzja=proposal, author=self.user, argument_type='FOR', content='Citizen argument')
        ZebranePodpisy.objects.create(projekt=proposal, podpis_uzytkownika=self.user)
        KtoJuzGlosowal.objects.create(projekt=proposal, ktory_uzytkownik_juz_zaglosowal=self.user)
        CitizenActivity.objects.create(uzytkownik=self.user.uzytkownik, activity_type=CitizenActivity.ActivityType.USER_ACTIVATED)
        RoomFactory(founder=self.user)

    def test_activity_service_preserves_source_order_for_ties_and_undated_items(self):
        self.create_activity_sources()
        Task.objects.filter(created_by=self.user).update(created_at=self.start, updated_at=self.start)
        for model, field in ((TaskVote, 'updated_at'), (TaskEvaluation, 'updated_at'), (Argument, 'created_at'), (CitizenActivity, 'timestamp')):
            model.objects.all().update(**{field: self.start})

        items = get_citizen_activity(self.user, self.user.uzytkownik)

        self.assertEqual([item['type'] for item in items], ['task_created', 'task_assigned', 'task_vote', 'task_eval', 'argument', 'citizen', 'signature', 'voted'])
        self.assertEqual([item['ts'] for item in items], [self.start] * 6 + [None, None])
        self.assertEqual(items, self.get_tab('aktywnosc').context['items'])

    def test_aggregation_service_query_counts_do_not_grow_with_rows(self):
        profile = self.user.uzytkownik
        total = 0
        for added in (1, 3):
            for _index in range(added):
                self.create_activity_sources()
            total += added
            room_count = Room.objects.filter(founder=self.user, public=True).count()
            with self.subTest(rows=total):
                with self.assertNumQueries(8):
                    activity = list(get_citizen_activity(self.user, profile))
                with self.assertNumQueries(3):
                    created = list(get_citizen_created_items(self.user))
                self.assertEqual(len(activity), total * 8)
                self.assertEqual(len(created), total * 2 + room_count)
                self.assertEqual(activity, self.get_tab('aktywnosc').context['items'])
                self.assertEqual(created, self.get_tab('zalozono').context['items'])

    def test_public_message_service_uses_one_query_and_excludes_anonymous_and_private(self):
        private = RoomFactory(public=False, founder=self.user)
        private.allowed.add(self.user, self.other)
        Message.objects.create(room=private, sender=self.user, text='Private')
        expected = []
        for added in (1, 3):
            for _index in range(added):
                room = RoomFactory(founder=self.user)
                expected.append(Message.objects.create(room=room, sender=self.user, text='Public'))
                Message.objects.create(room=room, sender=self.user, anonymous=True, text='Anonymous')
            with self.subTest(messages=len(expected)):
                with self.assertNumQueries(1):
                    rows = list(get_user_public_message_rows(self.user, self.other))
                self.assertCountEqual([row['msg'] for row in rows], expected)
                self.assertEqual(rows, self.get_tab('czaty').context['rows'])

    def test_user_tasks_service_returns_a_lazy_queryset(self):
        task = Task.objects.create(title='Both roles', created_by=self.user, assigned_to=self.user)
        with self.assertNumQueries(0):
            tasks = get_user_tasks(self.user)
            self.assertIsInstance(tasks, QuerySet)
            filtered = tasks.filter(pk=task.pk)
        with self.assertNumQueries(1):
            self.assertEqual(list(filtered), [task])
        self.assertEqual(list(tasks), list(self.get_tab('zadania').context['tasks']))

    def test_tab_endpoints_keep_login_and_not_found_guards(self):
        tabs = ('aktywnosc', 'zalozono', 'zadania', 'czaty')
        self.client.logout()
        for tab in tabs:
            with self.subTest(tab=tab, guard='login'):
                url = reverse(f'obywatele:citizen_{tab}', kwargs={'pk': self.user.pk})
                self.assertRedirects(self.client.get(url), f'{resolve_url(settings.LOGIN_URL)}?next={url}', fetch_redirect_response=False)
        self.client.force_login(self.other)
        missing_pk = User.objects.order_by('-pk').first().pk + 1
        for tab in tabs:
            with self.subTest(tab=tab, guard='unknown user'):
                self.assertEqual(self.client.get(reverse(f'obywatele:citizen_{tab}', kwargs={'pk': missing_pk})).status_code, 404)
        Uzytkownik.objects.filter(uid=self.user).delete()
        self.assertTrue(Uzytkownik.objects.filter(uid=self.other).exists())
        self.assertEqual(self.client.get(reverse('obywatele:citizen_aktywnosc', kwargs={'pk': self.user.pk})).status_code, 404)


class MyAssetsViewTest(TestCase):
    """my_assets zapisuje pola profilu przez form.save() oraz imię/nazwisko na User."""

    def setUp(self):
        self.user = User.objects.create_user(username='assets', password='secret', is_active=True)
        self.profile = self.user.uzytkownik
        self.profile.city = 'Stare miasto'
        self.profile.save()
        self.client.force_login(self.user)
        self.url = reverse('obywatele:my_assets')

    def test_get_prefills_form_from_instance(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.instance.pk, self.profile.pk)
        self.assertEqual(form['city'].value(), 'Stare miasto')
        self.assertEqual(form['first_name'].value(), self.user.first_name)

    def test_post_updates_existing_profile_and_user_names(self):
        response = self.client.post(self.url, PROFILE_POST_DATA)

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.profile.city, 'Gdańsk')
        self.assertEqual(self.profile.phone, '123456789')
        self.assertEqual(self.profile.for_sale, 'Kanapa')
        self.assertEqual(self.user.first_name, 'Jan')
        self.assertEqual(self.user.last_name, 'Kowalski')
        # Nadal ten sam rekord profilu — form.save() z instance= nie tworzy nowego.
        self.assertEqual(Uzytkownik.objects.filter(uid=self.user).count(), 1)

    def test_post_invalid_redirects_without_saving(self):
        data = {**PROFILE_POST_DATA, 'phone': ''}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.city, 'Stare miasto')


class DodajViewTest(TestCase):
    """dodaj tworzy kandydata z polami profilu z ONBOARDING_FORM_FIELDS."""

    def setUp(self):
        self.user = User.objects.create_user(username='proposer', password='secret', is_active=True)
        self.client.force_login(self.user)
        self.url = reverse('obywatele:zaproponuj_osobe')

    def test_post_creates_inactive_candidate_with_profile(self):
        data = {**PROFILE_POST_DATA, 'username': 'kandydat', 'email': 'kandydat@example.com'}

        with patch('obywatele.views.citizen_proposed'):
            response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        candidate = User.objects.get(username='kandydat')
        self.assertFalse(candidate.is_active)

        profile = candidate.uzytkownik
        self.assertEqual(profile.polecajacy, 'proposer')
        for field in Uzytkownik.ONBOARDING_FORM_FIELDS:
            self.assertEqual(getattr(profile, field) or '', PROFILE_POST_DATA[field])

        self.assertTrue(Rate.objects.filter(kandydat=profile, obywatel=self.user.uzytkownik, rate=1).exists())

    def test_post_rejects_duplicate_email(self):
        User.objects.create_user(username='istnieje', email='kandydat@example.com')
        data = {**PROFILE_POST_DATA, 'username': 'kandydat', 'email': 'KANDYDAT@example.com'}

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username='kandydat').exists())
