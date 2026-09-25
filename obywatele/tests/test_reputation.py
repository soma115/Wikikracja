"""Testy modelu Rate i wpływu na reputation Uzytkownika.

Reputation jest pochodną sumy Rate.rate gdzie kandydat = ten user. Test sprawdza że można
zbudować ten flow w ORM i że unique_together(kandydat, obywatel) zabezpiecza przed multi-vote.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from board.models import Post
from bookkeeping.models import Asset, Category, Partner, Transaction
from obywatele.models import Rate, Uzytkownik
from obywatele.services import release_blocked_user_resources
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


class BlockedUserResourcesTest(TestCase):
    def test_blocking_releases_tasks_documents_and_transactions(self):
        blocked = User.objects.create_user(username='blocked', email='blocked@example.com', password='x')
        task = Task.objects.create(title='Task', description='Description', assigned_to=blocked)
        task.approved_helpers.add(blocked)
        TaskVote.objects.create(task=task, user=blocked, value=TaskVote.Value.UP)
        down_task = Task.objects.create(title='Down task', description='Description')
        TaskVote.objects.create(task=down_task, user=blocked, value=TaskVote.Value.DOWN)
        post = Post.objects.create(title='Private', text='Text', author=blocked, visibility=Post.Visibility.PRIVATE)
        asset = Asset.objects.create(code='BLK', name='Blocked asset', symbol='B')
        category = Category.objects.create(name='Blocked category')
        partner = Partner.objects.create(name='Blocked partner')
        transaction = Transaction.objects.create(type='I', asset=asset, category=category, partner=partner, amount=10, author=blocked)

        release_blocked_user_resources(blocked)

        task.refresh_from_db()
        post.refresh_from_db()
        transaction.refresh_from_db()
        self.assertIsNone(task.assigned_to)
        self.assertFalse(task.approved_helpers.filter(pk=blocked.pk).exists())
        self.assertFalse(TaskVote.objects.filter(user=blocked).exists())
        self.assertEqual(post.visibility, Post.Visibility.GROUP)
        self.assertIsNone(transaction.author)
