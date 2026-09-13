import secrets
from datetime import datetime, timedelta
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

    def test_event_list_view(self):
        response = self.client.get(reverse('events:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Event")

    def test_event_detail_view(self):
        response = self.client.get(reverse('events:detail', kwargs={'pk': self.event.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Event")

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

    def test_past_event_is_visible_in_selected_month(self):
        past_event = Event.objects.create(title='Past Event', start_date=timezone.make_aware(datetime(2026, 6, 10, 10)), frequency='once')
        response = self.client.get(reverse('events:list'), {'month': '2026-06'})
        self.assertContains(response, past_event.title)
        self.assertNotContains(response, 'agenda-month-header')

    def test_event_from_next_month_is_not_visible(self):
        Event.objects.create(title='Next Month Event', start_date=timezone.make_aware(datetime(2026, 7, 1)), frequency='once')
        response = self.client.get(reverse('events:list'), {'month': '2026-06'})
        self.assertNotContains(response, 'Next Month Event')

    def test_agenda_chunk_loads_past_event_from_selected_month(self):
        start_date = timezone.now() - timedelta(days=60)
        past_event = Event.objects.create(title='Older Past Event', start_date=start_date, frequency='once')
        month = timezone.localtime(start_date).strftime('%Y-%m')
        response = self.client.get(reverse('events:agenda_chunk'), {'month': month}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, past_event.title)
