from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.presence import get_presence_status, record_presence


class PresenceStatusTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='presence-user', password='password')

    def test_status_uses_configured_default_thresholds(self):
        now = timezone.now()
        self.assertEqual(get_presence_status(now - timedelta(minutes=15), now=now), 'green')
        self.assertEqual(get_presence_status(now - timedelta(minutes=15, seconds=1), now=now), 'yellow')
        self.assertEqual(get_presence_status(now - timedelta(days=7), now=now), 'yellow')
        self.assertEqual(get_presence_status(now - timedelta(days=7, seconds=1), now=now), 'red')

    def test_missing_or_serialized_presence_is_safe(self):
        now = timezone.now()
        self.assertEqual(get_presence_status(None), 'red')
        self.assertEqual(get_presence_status(now.isoformat(), now=now), 'green')
        self.assertEqual(get_presence_status('not-a-date', now=now), 'red')

    def test_presence_is_monotonic_and_records_source(self):
        now = timezone.now()
        self.assertTrue(record_presence(self.user, 'app', timestamp=now))
        self.assertFalse(record_presence(self.user, 'push', timestamp=now - timedelta(seconds=1)))
        self.assertEqual(self.user.uzytkownik.last_presence_source, 'app')
        self.assertTrue(record_presence(self.user, 'push', timestamp=now + timedelta(seconds=1)))
        self.user.uzytkownik.refresh_from_db()
        self.assertEqual(self.user.uzytkownik.last_presence_source, 'push')

    def test_invalid_source_is_ignored(self):
        with patch('core.presence.timezone.now', return_value=timezone.now()):
            self.assertFalse(record_presence(self.user, 'invalid'))
        self.assertIsNone(self.user.uzytkownik.last_presence_at)
