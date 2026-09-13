from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from chat.models import Room


class CreateSystemRoomsCommandTest(TestCase):
    def setUp(self):
        Room.objects.filter(system_key__isnull=False).delete()

    def test_creates_both_system_rooms_when_missing(self):
        self.assertFalse(Room.objects.filter(system_key__isnull=False).exists())
        out = StringIO()
        call_command('create_inbox', stdout=out)

        inbox = Room.objects.get(system_key='inbox')
        important = Room.objects.get(system_key='important')
        self.assertEqual(inbox.title, 'Inbox')
        self.assertEqual(important.title, 'Ważne')
        for room in (inbox, important):
            self.assertTrue(room.public)
            self.assertTrue(room.protected)
            self.assertEqual(room.messages.count(), 1)
        self.assertEqual(inbox.source_app, '')
        self.assertIsNone(inbox.messages.first().sender)
        self.assertFalse(inbox.messages.first().anonymous)
        self.assertIn('System chat rooms ready', out.getvalue())

    def test_is_idempotent(self):
        out = StringIO()
        call_command('create_inbox', stdout=out)
        inbox_message = Room.objects.get(system_key='inbox').messages.first()
        important_message = Room.objects.get(system_key='important').messages.first()

        call_command('create_inbox', stdout=out)

        self.assertEqual(Room.objects.filter(system_key='inbox').count(), 1)
        self.assertEqual(Room.objects.filter(system_key='important').count(), 1)
        self.assertEqual(Room.objects.get(system_key='inbox').messages.first().pk, inbox_message.pk)
        self.assertEqual(Room.objects.get(system_key='important').messages.first().pk, important_message.pk)

    def test_creates_inbox_when_group_is_not_public(self):
        from site_settings.models import SiteParameters

        sp = SiteParameters.get()
        sp.group_is_public = False
        sp.save()
        call_command('create_inbox', stdout=StringIO())

        inbox = Room.objects.get(system_key='inbox')
        self.assertTrue(inbox.public)
        self.assertTrue(inbox.is_inbox)
