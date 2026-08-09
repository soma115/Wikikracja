"""Testy modelu Rate i wpływu na reputation Uzytkownika.

Reputation jest pochodną sumy Rate.rate gdzie kandydat = ten user. Test sprawdza że można
zbudować ten flow w ORM i że unique_together(kandydat, obywatel) zabezpiecza przed multi-vote.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from obywatele.models import Rate, Uzytkownik

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
