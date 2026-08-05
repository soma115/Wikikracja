from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event


class CalendarPartialEmptyDayTest(TestCase):
    """Puste dni w _calendar_partial.html powinny być klikalne (data-day + link do events:list)."""

    def setUp(self):
        self.user = User.objects.create_user(username='testowy', password='pass')
        self.client.login(username='testowy', password='pass')
        # Czerwiec 2026: dzień 10 na pewno nie ma eventów w domyślnej konfiguracji
        self.cal_url = reverse('events:calendar') + '?month=2026-06'

    def test_day_with_events_has_data_day_attribute(self):
        """Baseline: dzień z eventem ma data-day."""
        Event.objects.create(
            title='Wydarzenie',
            start_date=timezone.make_aware(datetime(2026, 6, 15, 10, 0)),
            frequency='once',
        )
        response = self.client.get(self.cal_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-day="2026-06-15"')

    def test_empty_day_has_data_day_attribute(self):
        """Dzień bez eventów ma atrybut data-day."""
        response = self.client.get(self.cal_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-day="2026-06-10"')

    def test_empty_day_is_link_to_events_list(self):
        """Dzień bez eventów jest linkiem do strony eventów z kotwicą dnia."""
        response = self.client.get(self.cal_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        events_url = reverse('events:list')
        self.assertContains(response, f'href="{events_url}#day-2026-06-10"')
