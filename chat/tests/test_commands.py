from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from chat.models import Room
from site_settings.models import SiteParameters


class CreateInboxCommandTest(TestCase):
    def setUp(self):
        Room.objects.filter(is_inbox=True).delete()

    def test_creates_inbox_when_missing(self):
        self.assertFalse(Room.objects.filter(is_inbox=True).exists())
        out = StringIO()
        call_command('create_inbox', stdout=out)
        self.assertTrue(Room.objects.filter(is_inbox=True).exists())
        room = Room.objects.get(is_inbox=True)
        self.assertEqual(room.title, 'Inbox')
        self.assertTrue(room.public)
        self.assertTrue(room.protected)
        self.assertIn('Created Inbox room', out.getvalue())

    def test_skips_when_inbox_exists(self):
        Room.objects.create(title='Inbox', public=True, protected=True, is_inbox=True)
        out = StringIO()
        call_command('create_inbox', stdout=out)
        self.assertEqual(Room.objects.filter(is_inbox=True).count(), 1)
        self.assertIn('already exists', out.getvalue())

    def test_skips_when_group_is_not_public(self):
        sp = SiteParameters.get()
        sp.group_is_public = False
        sp.save()
        out = StringIO()
        call_command('create_inbox', stdout=out)
        self.assertFalse(Room.objects.filter(is_inbox=True).exists())
        self.assertIn('GROUP_IS_PUBLIC is False', out.getvalue())
