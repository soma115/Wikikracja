import secrets
from datetime import timedelta

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

    def test_event_create_view_requires_login(self):
        response = self.client.get(reverse('events:create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_event_create_view_authenticated(self):
        self.client.login(username='testuser', password=self.test_password)
        response = self.client.get(reverse('events:create'))
        self.assertEqual(response.status_code, 200)

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
