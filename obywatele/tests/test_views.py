"""
Testy widoku set_user_language: wybór języka musi działać dla NIEzalogowanych
(strona startowa + cały proces zakładania konta), z trwałością przez cookie
`django_language`, a dla zalogowanych dodatkowo zapisywać się do profilu.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.models import QuerySet
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone as django_timezone
from django.utils.translation import gettext as _
from django.utils.translation import override, pgettext

from chat.models import Message, MessageReadBy, Room
from chat.services import get_user_public_message_rows
from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
from obywatele.auth_backends import CaseInsensitiveEmailBackend
from obywatele.forms import ProfileForm, phone_country_choices
from obywatele.models import CitizenActivity, DeletionRequest, PrivateNote, Rate, Uzytkownik
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


class CitizenListViewTest(TestCase):
    def test_grid_cards_include_only_active_tasks_coordinated_by_each_citizen(self):
        citizen = User.objects.create_user(username='coordinator', password='secret', is_active=True)
        other = User.objects.create_user(username='other-coordinator', password='secret', is_active=True)
        User.objects.create_user(username='empty-coordinator', password='secret', is_active=True)
        active_task = Task.objects.create(title='Active coordinated task', assigned_to=citizen)
        long_task_title = 'A very long coordinated task title ' * 4
        long_task = Task.objects.create(title=long_task_title, assigned_to=citizen)
        third_task = Task.objects.create(title='Third coordinated task', assigned_to=citizen)
        fourth_task = Task.objects.create(title='Fourth coordinated task', assigned_to=citizen)
        completed_task = Task.objects.create(title='Completed coordinated task', assigned_to=citizen, status=Task.Status.COMPLETED)
        Task.objects.create(title='Other person task', assigned_to=other)
        TaskVote.objects.create(task=active_task, user=other, value=TaskVote.Value.DOWN)
        TaskVote.objects.create(task=long_task, user=other, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=fourth_task, user=other, value=TaskVote.Value.DOWN)
        self.client.force_login(other)

        response = self.client.get(reverse('obywatele:obywatele'))

        self.assertEqual(response.status_code, 200)
        citizen_row = next(user for user in response.context['uid'] if user.pk == citizen.pk)
        self.assertEqual(list(citizen_row.coordinated_tasks), [long_task, third_task, active_task])
        self.assertContains(response, _('Business'))
        self.assertContains(response, _('Job'))
        self.assertContains(response, _('Hobby'))
        self.assertContains(response, '<span>-</span>', count=3)
        self.assertContains(response, active_task.title)
        self.assertContains(response, reverse('tasks:detail', kwargs={'pk': active_task.pk}))
        self.assertContains(response, long_task_title)
        self.assertContains(response, 'tw-block tw-w-full tw-min-w-0 tw-max-w-full tw-truncate')
        self.assertContains(response, f'title="{long_task_title}"')
        self.assertNotContains(response, fourth_task.title)
        self.assertNotContains(response, completed_task.title)

    def test_list_and_grid_show_pending_deletion_badge(self):
        viewer = User.objects.create_user(username='deletion-viewer', password='secret', is_active=True)
        citizen = User.objects.create_user(username='deletion-citizen', password='secret', is_active=True)
        DeletionRequest.objects.create(user=citizen, scheduled_for=django_timezone.now() + timedelta(days=1))
        self.client.force_login(viewer)

        response = self.client.get(reverse('obywatele:obywatele'))

        self.assertContains(response, f'title="{_("This person has requested account deletion")}"', count=2)

    def test_chat_button_shows_exact_unread_dm_count(self):
        viewer = User.objects.create_user(username='dm-viewer', password='secret', is_active=True)
        citizen = User.objects.create_user(username='dm-citizen', password='secret', is_active=True)
        room = Room.get_or_create_for_users(viewer, citizen)
        read_message = Message.objects.create(room=room, sender=citizen, text='Read')
        Message.objects.create(room=room, sender=citizen, text='Unread')
        MessageReadBy.objects.create(message=read_message, user=viewer)
        self.client.force_login(viewer)

        response = self.client.get(reverse('obywatele:obywatele'))

        citizen_row = next(user for user in response.context['uid'] if user.pk == citizen.pk)
        self.assertEqual(citizen_row.dm_unread_count, 1)
        self.assertContains(response, '<span class="tw-chat-count">1</span>')


class CitizenPresenceFilterTest(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username='presence-filter-viewer', is_active=True)
        now = django_timezone.now()
        self.online = self._create_with_presence('presence-filter-online', timedelta(minutes=1), 'app', now)
        self.recent = self._create_with_presence('presence-filter-recent', timedelta(days=1), 'push', now)
        self.inactive = self._create_with_presence('presence-filter-inactive', timedelta(days=8), 'app', now)
        self.no_signal = User.objects.create_user(username='presence-filter-no-signal', is_active=True)
        self.login_only = User.objects.create_user(username='presence-filter-login-only', is_active=True)
        User.objects.filter(pk=self.login_only.pk).update(last_login=now)
        self.login_only.uzytkownik.last_presence_at = now - timedelta(days=8)
        self.login_only.uzytkownik.save(update_fields=['last_presence_at'])
        self.client.force_login(self.viewer)

    @staticmethod
    def _create_with_presence(username, age, source, now):
        user = User.objects.create_user(username=username, is_active=True)
        profile = user.uzytkownik
        profile.last_presence_at = now - age
        profile.last_presence_source = source
        profile.save(update_fields=['last_presence_at', 'last_presence_source'])
        return user

    def _filtered_usernames(self, value):
        response = self.client.get(reverse('obywatele:obywatele'), {'aktywnosc': value})
        self.assertEqual(response.status_code, 200)
        return {user.username for user in response.context['uid'] if user.pk != self.viewer.pk}

    def test_filter_uses_app_and_push_presence_instead_of_last_login(self):
        self.assertEqual(self._filtered_usernames('online'), {self.online.username})
        self.assertEqual(self._filtered_usernames('7d'), {self.recent.username})
        self.assertEqual(self._filtered_usernames('nieaktywni'), {self.inactive.username, self.login_only.username, self.no_signal.username})

    def test_legacy_thirty_day_filter_is_removed(self):
        response = self.client.get(reverse('obywatele:obywatele'), {'aktywnosc': '30d'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['aktywnosc'], '')
        response = self.client.get(reverse('obywatele:obywatele'))
        self.assertContains(response, 'Nieaktywni 7+ dni')
        self.assertNotContains(response, 'Aktywni 30 dni')

    def test_partial_returns_only_replaceable_list_content(self):
        response = self.client.get(reverse('obywatele:obywatele'), {'aktywnosc': 'online', 'partial': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'obywatele/_citizens_list_content.html')
        self.assertContains(response, 'id="citizens-list-view"')
        self.assertNotContains(response, 'Szukaj użytkownika')


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


class PersonPushMuteViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='push-muter', password='secret', is_active=True)
        self.target = User.objects.create_user(username='push-target', password='secret', is_active=True)
        self.client.force_login(self.user)
        self.url = reverse('obywatele:toggle_person_push', kwargs={'pk': self.target.pk})

    def test_toggle_mutes_and_unmutes_target(self):
        response = self.client.post(self.url, data='{"enabled": false}', content_type='application/json')
        self.assertEqual(response.json(), {'success': True})
        self.assertTrue(self.user.uzytkownik.muted_push_users.filter(pk=self.target.pk).exists())

        response = self.client.post(self.url, data='{"enabled": true}', content_type='application/json')
        self.assertEqual(response.json(), {'success': True})
        self.assertFalse(self.user.uzytkownik.muted_push_users.filter(pk=self.target.pk).exists())

    def test_cannot_mute_self(self):
        url = reverse('obywatele:toggle_person_push', kwargs={'pk': self.user.pk})
        response = self.client.post(url, data='{"enabled": false}', content_type='application/json')
        self.assertEqual(response.status_code, 400)


class PrivateNoteViewTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='note-author', password='secret', is_active=True)
        self.subject = User.objects.create_user(username='note-subject', password='secret', is_active=True)
        self.client.force_login(self.author)
        self.url = reverse('obywatele:private_note', kwargs={'pk': self.subject.pk})

    def test_create_update_and_delete_note(self):
        detail_url = reverse('obywatele:obywatele_szczegoly', kwargs={'pk': self.subject.pk})
        response = self.client.post(self.url, {'content': 'First note'})
        self.assertRedirects(response, detail_url)
        note = PrivateNote.objects.get(author=self.author.uzytkownik, subject=self.subject.uzytkownik)
        self.assertEqual(note.content, 'First note')

        response = self.client.post(self.url, {'content': '  Updated note  \n  second line '})
        self.assertRedirects(response, detail_url)
        note.refresh_from_db()
        self.assertEqual(note.content, 'Updated note\nsecond line')

        response = self.client.post(self.url, {'content': '  '})
        self.assertRedirects(response, detail_url)
        self.assertFalse(PrivateNote.objects.filter(pk=note.pk).exists())

    def test_note_is_private_and_validates_length_and_self(self):
        response = self.client.post(self.url, {'content': 'x' * 501})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PrivateNote.objects.exists())

        self_url = reverse('obywatele:private_note', kwargs={'pk': self.author.pk})
        response = self.client.post(self_url, {'content': 'Self note'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PrivateNote.objects.exists())

        other = User.objects.create_user(username='other-note-author', password='secret', is_active=True)
        PrivateNote.objects.create(author=self.author.uzytkownik, subject=self.subject.uzytkownik, content='Only mine')
        self.client.force_login(other)
        detail = self.client.get(reverse('obywatele:obywatele_szczegoly', kwargs={'pk': self.subject.pk}))
        self.assertEqual(detail.context['person_private_note'], None)


class ProfileFormErrorViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profile-errors', email='old@example.com', password='secret', is_active=True)
        self.client.force_login(self.user)

    def test_change_email_rerenders_invalid_form(self):
        response = self.client.post(reverse('obywatele:change_email'), {'new_email1': 'new@example.com', 'new_email2': 'different@example.com'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertContains(response, 'new@example.com')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old@example.com')

    def test_change_username_rerenders_invalid_form(self):
        response = self.client.post(reverse('obywatele:change_username'), {'username': ''})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('username', response.context['form'].errors)

    def test_upload_avatar_reports_invalid_file(self):
        response = self.client.post(reverse('obywatele:upload_avatar'), {'avatar': SimpleUploadedFile('avatar.txt', b'not an image', content_type='text/plain')})

        self.assertRedirects(response, reverse('obywatele:my_profile'))
        self.assertFalse(self.user.uzytkownik.avatar)


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
        self.assertEqual(self.profile.phone, '+48123456789')
        self.assertEqual(self.profile.for_sale, 'Kanapa')
        self.assertEqual(self.user.first_name, 'Jan')
        self.assertEqual(self.user.last_name, 'Kowalski')
        # Nadal ten sam rekord profilu — form.save() z instance= nie tworzy nowego.
        self.assertEqual(Uzytkownik.objects.filter(uid=self.user).count(), 1)

    def test_post_invalid_rerenders_form_without_saving(self):
        data = {**PROFILE_POST_DATA, 'city': ''}
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertContains(response, _('The form could not be saved. Please correct the following errors:'))
        self.assertEqual(response.context['form']['city'].value(), '')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.city, 'Stare miasto')


class ContactPreferenceFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='contact-form', password='secret', is_active=True)
        self.profile = self.user.uzytkownik
        self.client.force_login(self.user)
        self.common = {**PROFILE_POST_DATA, 'first_name': 'Jan', 'last_name': 'Kowalski'}

    def test_link_contact_does_not_require_phone(self):
        data = {**self.common, 'phone': '', 'preferred_contact_method': 'signal', 'contact_link': 'https://signal.me/#p/example'}

        form = ProfileForm(data=data, instance=self.profile)

        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save()
        self.assertEqual(profile.phone, '')
        self.assertEqual(profile.preferred_contact_method, 'signal')

    def test_whatsapp_requires_and_normalizes_phone(self):
        data = {**self.common, 'phone': '501 234 567', 'phone_country': 'PL', 'preferred_contact_method': 'whatsapp', 'contact_link': ''}

        form = ProfileForm(data=data, instance=self.profile)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['phone'], '+48501234567')
        self.assertEqual(form.cleaned_data['phone_country'], 'PL')

    def test_phone_country_choices_use_full_country_names(self):
        choices = dict(phone_country_choices())

        self.assertEqual(choices['PL'], '+48 — Poland')
        self.assertEqual(choices['AC'], '+247 — Ascension Island')
        self.assertEqual(choices['US'], '+1 — United States')

    def test_existing_phone_is_displayed_without_country_prefix(self):
        self.profile.phone = '+48501234567'
        self.profile.phone_country = 'PL'
        self.profile.save()

        form = ProfileForm(instance=self.profile)

        self.assertEqual(form['phone'].value(), '501 234 567')

    def test_country_is_repaired_from_existing_phone_when_data_is_inconsistent(self):
        self.profile.phone = '+48123123123'
        self.profile.phone_country = 'AC'
        self.profile.save()

        form = ProfileForm(instance=self.profile)

        self.assertEqual(form['phone_country'].value(), 'PL')
        self.assertEqual(form['phone'].value(), '12 312 31 23')

    def test_local_phone_is_normalized_for_selected_country(self):
        data = {**self.common, 'phone': '123123', 'phone_country': 'AC', 'preferred_contact_method': 'phone', 'contact_link': ''}

        form = ProfileForm(data=data, instance=self.profile)

        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save()
        self.assertEqual(profile.phone, '+247123123')
        self.assertEqual(profile.phone_country, 'AC')

    def test_signal_accepts_phone_without_profile_link(self):
        data = {**self.common, 'phone': '501 234 567', 'phone_country': 'PL', 'preferred_contact_method': 'signal', 'contact_link': ''}

        form = ProfileForm(data=data, instance=self.profile)

        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save()
        self.assertEqual(profile.contact_url, 'https://signal.me/#p/+48501234567')

    def test_view_saves_and_restores_contact_preference(self):
        data = {**self.common, 'phone': '501 234 567', 'phone_country': 'PL', 'preferred_contact_method': 'signal', 'contact_link': ''}

        response = self.client.post(reverse('obywatele:my_assets'), data)

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.preferred_contact_method, 'signal')
        response = self.client.get(reverse('obywatele:my_assets'))
        self.assertEqual(response.context['form']['preferred_contact_method'].value(), 'signal')


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
            expected = '+48123456789' if field == 'phone' else PROFILE_POST_DATA[field]
            self.assertEqual(getattr(profile, field) or '', expected)

        self.assertTrue(Rate.objects.filter(kandydat=profile, obywatel=self.user.uzytkownik, rate=1).exists())

    def test_post_rejects_duplicate_email(self):
        User.objects.create_user(username='istnieje', email='kandydat@example.com')
        data = {**PROFILE_POST_DATA, 'username': 'kandydat', 'email': 'KANDYDAT@example.com'}

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username='kandydat').exists())


class CitizenPresenceTemplateTest(TestCase):
    def test_citizen_list_renders_presence_colors(self):
        viewer = User.objects.create_user(username='presence-viewer', password='secret', is_active=True)
        green = User.objects.create_user(username='presence-green', is_active=True)
        yellow = User.objects.create_user(username='presence-yellow', is_active=True)
        red = User.objects.create_user(username='presence-red', is_active=True)
        now = django_timezone.now()
        green.uzytkownik.last_presence_at = now
        green.uzytkownik.last_presence_source = 'app'
        green.uzytkownik.save(update_fields=['last_presence_at', 'last_presence_source'])
        yellow.uzytkownik.last_presence_at = now - timedelta(days=1)
        yellow.uzytkownik.last_presence_source = 'push'
        yellow.uzytkownik.save(update_fields=['last_presence_at', 'last_presence_source'])
        red.uzytkownik.last_presence_at = now - timedelta(days=8)
        red.uzytkownik.last_presence_source = 'app'
        red.uzytkownik.save(update_fields=['last_presence_at', 'last_presence_source'])

        self.client.force_login(viewer)
        response = self.client.get(reverse('obywatele:obywatele'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tw-presence-green')
        self.assertContains(response, 'tw-presence-yellow')
        self.assertContains(response, 'tw-presence-red')

    def test_citizen_list_query_count_does_not_grow_with_users(self):
        viewer = User.objects.create_user(username='query-viewer', password='secret', is_active=True)
        User.objects.create_user(username='query-citizen-1', is_active=True)
        self.client.force_login(viewer)
        with CaptureQueriesContext(connection) as one_user_context:
            self.client.get(reverse('obywatele:obywatele'))

        User.objects.create_user(username='query-citizen-2', is_active=True)
        User.objects.create_user(username='query-citizen-3', is_active=True)
        with CaptureQueriesContext(connection) as three_users_context:
            self.client.get(reverse('obywatele:obywatele'))

        self.assertLessEqual(len(three_users_context), len(one_user_context) + 1)

    def test_dashboard_activity_pulse_uses_presence_recency(self):
        from obywatele.dashboard import get_context

        viewer = User.objects.create_user(username='dashboard-viewer', is_active=True)
        green = User.objects.create_user(username='dashboard-green', is_active=True)
        yellow = User.objects.create_user(username='dashboard-yellow', is_active=True)
        recent = User.objects.create_user(username='dashboard-recent', is_active=True)
        now = django_timezone.now()
        green.uzytkownik.last_presence_at = now
        green.uzytkownik.save(update_fields=['last_presence_at'])
        yellow.uzytkownik.last_presence_at = now - timedelta(days=1)
        yellow.uzytkownik.save(update_fields=['last_presence_at'])
        recent.uzytkownik.last_presence_at = now - timedelta(days=10)
        recent.uzytkownik.save(update_fields=['last_presence_at'])

        context = get_context(viewer)

        self.assertEqual(context['active_green'], 1)
        self.assertEqual(context['active_yellow'], 1)
        self.assertEqual(context['active_recent'], 1)
        self.assertEqual(context['active_last_month'], 3)


class AccountDeletionFeedbackTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='leaving', password='secret', first_name='Leaving', last_name='Member')
        self.client.force_login(self.user)
        self.url = reverse('obywatele:request_deletion')

    @patch('obywatele.views.publish_deletion_feedback')
    def test_immediate_feedback_is_published_and_not_kept_on_request(self, publish):
        response = self.client.post(self.url, {'reason': 'Brakuje mi spokojniejszej dyskusji.', 'publication_timing': 'now', 'publication_identity': 'named'})

        self.assertEqual(response.status_code, 302)
        publish.assert_called_once_with('Brakuje mi spokojniejszej dyskusji.', anonymous=False, author_name='Leaving Member')
        deletion = DeletionRequest.objects.get(user=self.user)
        self.assertEqual(deletion.reason, '')
        self.assertFalse(deletion.publish_after_deletion)
        self.assertFalse(deletion.publish_anonymously)

    @patch('obywatele.views.publish_deletion_feedback')
    def test_delayed_feedback_is_kept_until_deletion(self, publish):
        self.client.post(self.url, {'reason': 'Potrzebuję innego trybu współpracy.', 'publication_timing': 'after_deletion', 'publication_identity': 'anonymous'})

        publish.assert_not_called()
        deletion = DeletionRequest.objects.get(user=self.user)
        self.assertEqual(deletion.reason, 'Potrzebuję innego trybu współpracy.')
        self.assertTrue(deletion.publish_after_deletion)
        self.assertTrue(deletion.publish_anonymously)

    def test_canceling_deletion_removes_delayed_feedback(self):
        self.client.post(self.url, {'reason': 'Jeszcze się zastanowię.', 'publication_timing': 'after_deletion', 'publication_identity': 'anonymous'})

        response = self.client.post(reverse('obywatele:cancel_deletion'))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(DeletionRequest.objects.filter(user=self.user).exists())

    @patch('obywatele.management.commands.count_citizens.citizen_deleted.send')
    @patch('obywatele.management.commands.count_citizens.publish_deletion_feedback')
    def test_delayed_feedback_is_published_after_account_deletion(self, publish, deleted_signal):
        from obywatele.management.commands.count_citizens import Command

        user_id = self.user.id
        DeletionRequest.objects.create(
            user=self.user, scheduled_for=django_timezone.now() - timedelta(days=1), reason='Nie odnajduję się już w tej formule.', publish_after_deletion=True, publish_anonymously=False
        )

        def assert_account_is_gone(*args, **kwargs):
            self.assertFalse(User.objects.filter(pk=user_id).exists())

        publish.side_effect = assert_account_is_gone
        Command().process_deletion_requests()

        deleted_signal.assert_called_once()
        publish.assert_called_once_with('Nie odnajduję się już w tej formule.', anonymous=False, author_name='Leaving Member')
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(DeletionRequest.objects.exists())
