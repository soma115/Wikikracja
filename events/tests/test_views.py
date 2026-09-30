import secrets
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event


class EventViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Generate secure random password for tests
        self.test_password = secrets.token_urlsafe(16)
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password=self.test_password)
        self.event = Event.objects.create(title="Test Event", description="Test Description", start_date=timezone.now() + timedelta(days=1), frequency='once')

    def create_event_on_date(self, title, date):
        return Event.objects.create(title=title, start_date=timezone.make_aware(datetime.combine(date, time(hour=12))), frequency='once')

    def create_event_at_offset(self, title, days):
        return self.create_event_on_date(title, timezone.localdate() + timedelta(days=days))

    def test_event_list_view(self):
        response = self.client.get(reverse('events:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Event")
        self.assertNotContains(response, 'tw-stepper-nav')
        self.assertContains(response, 'data-view="grid"')
        self.assertContains(response, 'data-view="list"')
        self.assertContains(response, 'data-default-view="grid"')

    def test_event_list_shows_selected_month_and_31_future_days(self):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        previous_month = month_start - timedelta(days=1)
        visible_titles = ('Month Start', 'Today', 'In 31 Days')
        for title, date in (('Month Start', month_start), ('Today', today), ('In 31 Days', today + timedelta(days=31))):
            self.create_event_on_date(title, date)
        self.create_event_on_date('Previous Month', previous_month)
        self.create_event_at_offset('In 32 Days', 32)

        response = self.client.get(reverse('events:list'), {'month': today.strftime('%Y-%m')})

        for title in visible_titles:
            self.assertContains(response, title)
        self.assertContains(response, 'class="tw-cal-day tw-cal-day-has-event tw-cal-day-today"')
        self.assertNotContains(response, 'Previous Month')
        self.assertNotContains(response, 'In 32 Days')

    def test_event_list_uses_month_selected_in_calendar(self):
        month_start = timezone.localdate().replace(day=1)
        selected_month_end = month_start - timedelta(days=1)
        selected_month_start = selected_month_end.replace(day=1)
        selected_month_event = self.create_event_on_date('Selected Month Start', selected_month_start)
        older_event = self.create_event_on_date('Before Selected Month', selected_month_start - timedelta(days=1))

        response = self.client.get(reverse('events:list'), {'month': selected_month_start.strftime('%Y-%m')})

        self.assertContains(response, selected_month_event.title)
        self.assertNotContains(response, older_event.title)

    def test_event_detail_view(self):
        response = self.client.get(reverse('events:detail', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Event")
        self.assertNotContains(response, 'tw-stepper-nav')

    def test_event_detail_navigation_preserves_month_and_occurrence(self):
        events = [Event.objects.create(title=f'Navigation {day}', start_date=timezone.make_aware(datetime(2030, 9, day, 10)), frequency='once') for day in (1, 2, 3)]
        occurrence_query = urlencode({'occurrence': events[1].start_date.isoformat()})

        response = self.client.get(f"{reverse('events:detail', args=[events[1].pk])}?month=2030-09&{occurrence_query}")

        previous_query = urlencode({'month': '2030-09', 'occurrence': events[0].start_date.astimezone(dt_timezone.utc).isoformat()})
        next_query = urlencode({'month': '2030-09', 'occurrence': events[2].start_date.astimezone(dt_timezone.utc).isoformat()})
        self.assertEqual(response.context['previous_url'], f"{reverse('events:detail', args=[events[0].pk])}?{previous_query}")
        self.assertEqual(response.context['next_url'], f"{reverse('events:detail', args=[events[2].pk])}?{next_query}")

    def test_event_create_view_requires_login(self):
        response = self.client.get(reverse('events:create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_event_create_view_authenticated(self):
        self.client.login(username='testuser', password=self.test_password)
        response = self.client.get(reverse('events:create'))
        self.assertEqual(response.status_code, 200)

    def test_new_event_defaults_to_today_at_noon(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('events:create'))

        start_date = timezone.localtime(response.context['form'].initial['start_date'])
        self.assertEqual(start_date.date(), timezone.localdate())
        self.assertEqual(start_date.time(), time(hour=12))

    def test_new_event_uses_selected_calendar_day_at_noon(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('events:create'), {'date': '2030-08-17'})

        start_date = timezone.localtime(response.context['form'].initial['start_date'])
        self.assertEqual(start_date.date().isoformat(), '2030-08-17')
        self.assertEqual(start_date.time(), time(hour=12))

    def test_event_form_uses_shared_edit_layout(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('events:edit', args=[self.event.pk]))

        self.assertContains(response, 'tw-container tw-my-4')
        self.assertContains(response, 'tw-card-header')
        self.assertContains(response, 'tw-btn tw-btn-primary')
        self.assertContains(response, 'tw-stepper-nav')
        self.assertNotContains(response, 'Back to Calendar')
        self.assertNotContains(response, 'tw-event-back-link')

    def test_event_edit_invalid_title_rerenders_form_without_saving(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('events:edit', args=[self.event.pk]),
            {
                'title': '',
                'description': 'Updated description',
                'link': '',
                'place': '',
                'start_date': '2030-01-01T10:00',
                'end_date': '',
                'frequency': 'once',
                'ordinal': '',
                'weekday': '',
                'is_active': 'on',
                'is_public': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Test Event')

    def test_any_logged_in_user_can_edit_event(self):
        other = User.objects.create_user(username='event-editor', email='event-editor@example.com', password='x')
        self.client.force_login(other)
        response = self.client.post(
            reverse('events:edit', args=[self.event.pk]),
            {
                'title': 'Updated by other',
                'description': '',
                'link': '',
                'place': '',
                'start_date': '2030-01-01T10:00',
                'end_date': '',
                'frequency': 'once',
                'ordinal': '',
                'weekday': '',
                'is_active': 'on',
                'is_public': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Updated by other')

    def test_private_event_hidden_in_list_for_anonymous(self):
        from events.models import Event as E

        E.objects.create(title="Private Event", start_date=timezone.now() + timedelta(days=1), frequency='once', is_public=False)
        response = self.client.get(reverse('events:list'))
        self.assertNotContains(response, "Private Event")

    def test_private_event_detail_returns_404_for_anonymous(self):
        from events.models import Event as E

        private = E.objects.create(title="Private Detail", start_date=timezone.now() + timedelta(days=1), frequency='once', is_public=False)
        response = self.client.get(reverse('events:detail', kwargs={'pk': private.pk}))
        self.assertEqual(response.status_code, 404)

    def test_private_event_visible_for_logged_in_user(self):
        from events.models import Event as E

        E.objects.create(title="Private Visible", start_date=timezone.now() + timedelta(days=1), frequency='once', is_public=False)
        self.client.login(username='testuser', password=self.test_password)
        response = self.client.get(reverse('events:list'))
        self.assertContains(response, "Private Visible")

    def test_event_beyond_31_day_future_window_is_not_visible(self):
        future_event = self.create_event_at_offset('Outside Event', 32)
        response = self.client.get(reverse('events:list'))
        self.assertNotContains(response, future_event.title)

    def test_agenda_chunk_uses_selected_month_and_31_future_days(self):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        past_event = self.create_event_on_date('Month Start Event', month_start)
        older_event = self.create_event_on_date('Previous Month Event', month_start - timedelta(days=1))
        future_event = self.create_event_at_offset('Future Boundary Event', 31)
        outside_event = self.create_event_at_offset('Outside Future Event', 32)
        response = self.client.get(reverse('events:agenda_chunk'), {'month': today.strftime('%Y-%m')}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, past_event.title)
        self.assertContains(response, future_event.title)
        self.assertNotContains(response, older_event.title)
        self.assertNotContains(response, outside_event.title)
