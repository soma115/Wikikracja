from datetime import datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from events.models import Event


class EventModelTest(TestCase):
    def setUp(self):
        self.event = Event.objects.create(title="Test Event", description="Test Description", start_date=timezone.now() + timedelta(days=1), frequency='weekly')

    def test_event_str(self):
        self.assertEqual(str(self.event), "Test Event")

    def test_get_absolute_url(self):
        url = self.event.get_absolute_url()
        self.assertEqual(url, f'/events/{self.event.pk}/')

    def test_is_upcoming(self):
        self.assertTrue(self.event.is_upcoming())

    def test_get_next_occurrence_weekly(self):
        next_occurrence = self.event.get_next_occurrence()
        self.assertIsNotNone(next_occurrence)

    def test_is_upcoming_false_when_inactive(self):
        self.event.is_active = False
        self.event.save()
        self.assertFalse(self.event.is_upcoming())

    def test_get_next_occurrence_once_past_returns_none(self):
        past_event = Event.objects.create(title="Past Event", start_date=timezone.now() - timedelta(days=1), frequency='once')
        self.assertIsNone(past_event.get_next_occurrence())

    def test_get_next_occurrence_once_future_returns_date(self):
        future_event = Event.objects.create(title="Future Event", start_date=timezone.now() + timedelta(days=7), frequency='once')
        self.assertIsNotNone(future_event.get_next_occurrence())

    def test_get_next_occurrence_yearly_returns_future(self):
        yearly_event = Event.objects.create(title="Yearly Event", start_date=timezone.now() - timedelta(days=365), frequency='yearly')
        next_occ = yearly_event.get_next_occurrence()
        self.assertIsNotNone(next_occ)
        self.assertGreater(next_occ, timezone.now())

    def test_get_next_occurrence_monthly_ordinal_none_fields_returns_none(self):
        event = Event.objects.create(title="Ordinal No Fields", start_date=timezone.now() + timedelta(days=1), frequency='monthly_ordinal', monthly_ordinal=None, monthly_weekday=None)
        self.assertIsNone(event.get_next_occurrence())

    def test_monthly_occurrences_clamp_to_last_day_without_drifting(self):
        event = Event.objects.create(title='Month End', start_date=timezone.make_aware(datetime(2026, 1, 31, 10)), frequency='monthly')

        occurrences = event.get_occurrences(timezone.make_aware(datetime(2026, 2, 1)), timezone.make_aware(datetime(2026, 4, 1)))

        self.assertEqual([occurrence.day for occurrence in occurrences], [28, 31])

    def test_yearly_occurrences_clamp_february_29_in_non_leap_years(self):
        event = Event.objects.create(title='Leap Day', start_date=timezone.make_aware(datetime(2024, 2, 29, 10)), frequency='yearly')

        occurrences = event.get_occurrences(timezone.make_aware(datetime(2025, 1, 1)), timezone.make_aware(datetime(2027, 3, 1)))

        self.assertEqual([(occurrence.year, occurrence.month, occurrence.day) for occurrence in occurrences], [(2025, 2, 28), (2026, 2, 28), (2027, 2, 28)])
