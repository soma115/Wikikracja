"""Testy modelu Rate i wpływu na reputation Uzytkownika.

Reputation jest pochodną sumy Rate.rate gdzie kandydat = ten user. Test sprawdza że można
zbudować ten flow w ORM i że unique_together(kandydat, obywatel) zabezpiecza przed multi-vote.
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from board.models import Post
from bookkeeping.models import Category, Partner, Transaction
from obywatele.management.commands.count_citizens import Command as CountCitizensCommand
from obywatele.models import Rate, Uzytkownik
from obywatele.services import release_blocked_user_resources
from resources.models import Entity
from tasks.models import Task, TaskVote

User = get_user_model()


class RateAndReputationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # UWAGA: obywatele.models ma signal post_save(User) który auto-tworzy Uzytkownik.
        # Nie wolno tworzyć ręcznie Uzytkownik.objects.create(uid=user) — tylko pobieramy.
        cls.candidate_user = User.objects.create_user(username='candidate', email='cand@example.com', password='x')
        cls.rater_users = [User.objects.create_user(username=f'rater{i}', email=f'r{i}@example.com', password='x') for i in range(3)]

        cls.candidate = Uzytkownik.objects.get(uid=cls.candidate_user)
        cls.candidate.reputation = 0
        cls.candidate.save()
        cls.raters = [Uzytkownik.objects.get(uid=u) for u in cls.rater_users]

    def test_rate_unique_per_kandydat_obywatel_pair(self):
        """unique_together(kandydat, obywatel) zabezpiecza przed wielokrotnym głosowaniem tej samej pary."""
        Rate.objects.create(kandydat=self.candidate, obywatel=self.raters[0], rate=3)

        with self.assertRaises(IntegrityError):
            Rate.objects.create(kandydat=self.candidate, obywatel=self.raters[0], rate=-2)

    def test_reputation_updated_from_sum_of_rates(self):
        """Po zsumowaniu Rate.rate można ustawić Uzytkownik.reputation i odczytać."""
        Rate.objects.create(kandydat=self.candidate, obywatel=self.raters[0], rate=5)
        Rate.objects.create(kandydat=self.candidate, obywatel=self.raters[1], rate=-2)
        Rate.objects.create(kandydat=self.candidate, obywatel=self.raters[2], rate=3)

        total = sum(r.rate for r in Rate.objects.filter(kandydat=self.candidate))
        self.assertEqual(total, 6)

        self.candidate.reputation = total
        self.candidate.save()
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.reputation, 6)

    def test_rate_count_equals_rater_count(self):
        """Liczba Rate dla kandydata == liczba unikalnych raterów."""
        for rater in self.raters:
            Rate.objects.create(kandydat=self.candidate, obywatel=rater, rate=1)

        self.assertEqual(Rate.objects.filter(kandydat=self.candidate).count(), len(self.raters))


class ActivationPasswordTest(TestCase):
    def test_activated_account_keeps_password_reset_eligible_without_emailing_password(self):
        user = User.objects.create_user(username='activation-password', email='activation@example.com', password='hidden-random-secret', is_active=False)
        profile = user.uzytkownik
        profile.reputation = 1
        profile.reputation_blocked_at = timezone.now() - timedelta(days=1)
        profile.save(update_fields=['reputation', 'reputation_blocked_at'])
        welcome_post = SimpleNamespace(text='Login: {login_url}; legacy password: {password}', get_display_title=lambda: 'Welcome')
        command = CountCitizensCommand()

        with (
            patch('obywatele.management.commands.count_citizens.required_reputation', return_value=0),
            patch.object(command, 'grant_automatic_reputation'),
            patch('obywatele.management.commands.count_citizens.Post.get_system_post', return_value=welcome_post),
            patch('obywatele.management.commands.count_citizens.get_site_domain', return_value='example.test'),
            patch('obywatele.management.commands.count_citizens.build_site_url', side_effect=lambda path: f'https://example.test{path}'),
            patch('obywatele.management.commands.count_citizens.get_user_language', return_value='en'),
            patch('obywatele.management.commands.count_citizens.citizen_accepted.send') as accepted,
        ):
            command.activate_eligible_users()

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(profile.reputation_blocked_at)
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password('hidden-random-secret'))
        email_body = accepted.call_args.kwargs['recipient_body']
        self.assertIn('legacy password: ', email_body)
        self.assertNotIn('hidden-random-secret', email_body)
        self.assertIn('https://example.test/password_reset/', email_body)


class BlockedUserResourcesTest(TestCase):
    def test_blocking_releases_tasks_documents_and_transactions(self):
        blocked = User.objects.create_user(username='blocked', email='blocked@example.com', password='x')
        task = Task.objects.create(title='Task', description='Description', assigned_to=blocked)
        task.approved_helpers.add(blocked)
        TaskVote.objects.create(task=task, user=blocked, value=TaskVote.Value.UP)
        down_task = Task.objects.create(title='Down task', description='Description')
        TaskVote.objects.create(task=down_task, user=blocked, value=TaskVote.Value.DOWN)
        post = Post.objects.create(title='Group document', text='Text', author=blocked, visibility=Post.Visibility.GROUP)
        asset = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, code='BLK', name='Blocked asset', symbol='B')
        category = Category.objects.create(name='Blocked category')
        partner = Partner.objects.create(name='Blocked partner')
        transaction = Transaction.objects.create(type='I', entity=asset, category=category, partner=partner, amount=10, author=blocked)

        release_blocked_user_resources(blocked)

        task.refresh_from_db()
        post.refresh_from_db()
        transaction.refresh_from_db()
        self.assertIsNone(task.assigned_to)
        self.assertFalse(task.approved_helpers.filter(pk=blocked.pk).exists())
        self.assertFalse(TaskVote.objects.filter(user=blocked).exists())
        self.assertEqual(post.visibility, Post.Visibility.GROUP)
        self.assertIsNone(transaction.author)


class ReputationBlockedGracePeriodTest(TestCase):
    def make_inactive_user(self, username, *, blocked_at=None, last_login=None, accepted=False):
        user = User.objects.create_user(username=username, email=f'{username}@example.com', password='x', is_active=False, last_login=last_login)
        profile = user.uzytkownik
        profile.reputation_blocked_at = blocked_at
        if accepted:
            profile.data_przyjecia = timezone.now().date()
        profile.save(update_fields=['reputation_blocked_at', 'data_przyjecia'])
        return user

    def test_blocking_starts_grace_period_and_prevents_same_run_deletion(self):
        user = User.objects.create_user(username='blocked-grace', email='blocked-grace@example.com', password='x')
        user.uzytkownik.reputation = 0
        user.uzytkownik.save(update_fields=['reputation'])
        started_before = timezone.now()

        with (
            patch('obywatele.management.commands.count_citizens.required_reputation', return_value=1),
            patch('obywatele.management.commands.count_citizens.invalidate_user_sessions'),
            patch('obywatele.management.commands.count_citizens.release_blocked_user_resources'),
            patch('obywatele.management.commands.count_citizens.get_site_domain', return_value='example.test'),
            patch('obywatele.management.commands.count_citizens.get_user_language', return_value='en'),
            patch('obywatele.management.commands.count_citizens.build_site_url', side_effect=lambda path: f'https://example.test{path}'),
            patch('obywatele.management.commands.count_citizens.citizen_blocked.send'),
            patch('site_settings.params.get_param', return_value=30),
            patch('obywatele.management.commands.count_citizens.citizen_deleted.send') as deleted_signal,
        ):
            command = CountCitizensCommand()
            command.block_ineligible_users()
            command.delete_inactive_users()

        user.refresh_from_db()
        profile = user.uzytkownik
        profile.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertGreaterEqual(profile.reputation_blocked_at, started_before)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        deleted_signal.assert_not_called()

    def test_cleanup_uses_reputation_block_time_and_preserves_candidate_cleanup(self):
        current_time = timezone.now()
        within_grace = self.make_inactive_user('within-grace', blocked_at=current_time - timedelta(days=29), last_login=current_time - timedelta(days=90), accepted=True)
        expired_block = self.make_inactive_user('expired-block', blocked_at=current_time - timedelta(days=31), last_login=current_time, accepted=True)
        expired_candidate = self.make_inactive_user('expired-candidate', last_login=current_time - timedelta(days=31))

        with patch('site_settings.params.get_param', return_value=30), patch('obywatele.management.commands.count_citizens.citizen_deleted.send'):
            CountCitizensCommand().delete_inactive_users()

        self.assertTrue(User.objects.filter(pk=within_grace.pk).exists())
        self.assertFalse(User.objects.filter(pk=expired_block.pk).exists())
        self.assertFalse(User.objects.filter(pk=expired_candidate.pk).exists())

    def test_existing_inactive_former_member_receives_full_grace_period(self):
        old_login = timezone.now() - timedelta(days=365)
        user = self.make_inactive_user('legacy-blocked', last_login=old_login, accepted=True)

        with patch('site_settings.params.get_param', return_value=30), patch('obywatele.management.commands.count_citizens.citizen_deleted.send') as deleted_signal:
            CountCitizensCommand().delete_inactive_users()

        user.refresh_from_db()
        profile = user.uzytkownik
        profile.refresh_from_db()
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertGreaterEqual(profile.reputation_blocked_at, timezone.now() - timedelta(minutes=1))
        deleted_signal.assert_not_called()
