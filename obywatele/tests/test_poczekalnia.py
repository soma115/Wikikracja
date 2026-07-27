"""Testy widoku poczekalnia i liczenia ocen kandydatów."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from obywatele.models import Rate, Uzytkownik

User = get_user_model()


class PoczekalniaRatingsTest(TestCase):
    def setUp(self):
        self.citizen_user = User.objects.create_user(
            username='citizen', email='citizen@example.com', password='secret', is_active=True
        )
        self.citizen = Uzytkownik.objects.get(uid=self.citizen_user)

        self.candidate1_user = User.objects.create_user(
            username='cand1', email='cand1@example.com', password='secret', is_active=False
        )
        self.candidate2_user = User.objects.create_user(
            username='cand2', email='cand2@example.com', password='secret', is_active=False
        )
        self.candidate1 = Uzytkownik.objects.get(uid=self.candidate1_user)
        self.candidate2 = Uzytkownik.objects.get(uid=self.candidate2_user)

        self.client.force_login(self.citizen_user)

    def test_opening_waiting_room_does_not_create_rate_records(self):
        """Otwarcie /poczekalnia/ nie powinno tworzyć rekordów Rate."""
        self.client.get(reverse('obywatele:poczekalnia'))

        self.assertEqual(Rate.objects.count(), 0)

    def test_rating_counts_are_individual_per_candidate(self):
        """Głos na jednego kandydata nie powinien zmieniać liczników innych."""
        # Głos pozytywny na kandydata 1
        self.client.post(
            reverse('obywatele:poczekalnia_szczegoly', kwargs={'pk': self.candidate1_user.pk}),
            {'action': 'accept'},
        )

        # Głos neutralny na kandydata 2
        self.client.post(
            reverse('obywatele:poczekalnia_szczegoly', kwargs={'pk': self.candidate2_user.pk}),
            {'action': 'reset'},
        )

        response = self.client.get(reverse('obywatele:poczekalnia'))

        self.assertEqual(response.status_code, 200)
        candidates = {u.pk: u for u in response.context['uid']}

        # candidate1: 1 positive / 0 neutral / 0 negative
        self.assertEqual(candidates[self.candidate1_user.pk].ratings_positive, 1)
        self.assertEqual(candidates[self.candidate1_user.pk].ratings_neutral, 0)
        self.assertEqual(candidates[self.candidate1_user.pk].ratings_negative, 0)

        # candidate2: 0 positive / 1 neutral / 0 negative
        self.assertEqual(candidates[self.candidate2_user.pk].ratings_positive, 0)
        self.assertEqual(candidates[self.candidate2_user.pk].ratings_neutral, 1)
        self.assertEqual(candidates[self.candidate2_user.pk].ratings_negative, 0)

    def test_neutral_count_only_includes_explicit_neutral_votes(self):
        """Licznik neutralnych ocen liczy tylko explicit kliknięcia 'Indifferent'."""
        # Pozytywny głos
        Rate.objects.create(kandydat=self.candidate1, obywatel=self.citizen, rate=1)
        # Nie tworzymy rekordu rate=0 tylko przez oglądanie — to byłby błąd

        response = self.client.get(reverse('obywatele:poczekalnia'))
        candidates = {u.pk: u for u in response.context['uid']}

        self.assertEqual(candidates[self.candidate1_user.pk].ratings_positive, 1)
        self.assertEqual(candidates[self.candidate1_user.pk].ratings_neutral, 0)
        self.assertEqual(candidates[self.candidate1_user.pk].ratings_negative, 0)
