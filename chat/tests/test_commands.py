from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from chat.management.commands.repair_discussion_rooms import Command as RepairDiscussionRoomsCommand
from chat.models import Message, Room
from chat.tests.utils import make_user
from tasks.models import Task
from tasks.tests.utils import make_task
from tests.factories import PostFactory


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


class ChatRoomsArchivingCommandTest(TestCase):
    def test_archives_old_empty_public_rooms_using_last_activity(self):
        old_room = Room.objects.create(title='Old empty room', public=True, protected=True)
        recent_room = Room.objects.create(title='Recent empty room', public=True, protected=True)
        old_activity = timezone.now() - timedelta(days=30)
        Room.objects.filter(pk=old_room.pk).update(last_activity=old_activity)

        params = {'archive_public_chat_room': 9, 'delete_public_chat_room': 360}
        with patch('site_settings.params.get_param', side_effect=params.__getitem__):
            call_command('chat_rooms')

        old_room.refresh_from_db()
        recent_room.refresh_from_db()
        self.assertTrue(old_room.archived)
        self.assertFalse(recent_room.archived)
        self.assertEqual(old_room.last_activity, old_activity)

    def test_deletes_old_unprotected_public_room_without_recreating_it(self):
        room = Room.objects.create(title='Old public room', public=True)
        message = Message.objects.create(room=room, text='Old message')
        Message.objects.filter(pk=message.pk).update(time=timezone.now() - timedelta(days=400))

        params = {'archive_public_chat_room': 9, 'delete_public_chat_room': 360}
        with patch('site_settings.params.get_param', side_effect=params.__getitem__):
            call_command('chat_rooms')

        self.assertFalse(Room.objects.filter(title=room.title).exists())

    def test_old_inactive_direct_message_is_still_deleted(self):
        active_user = make_user('old-dm-active')
        inactive_user = make_user('old-dm-inactive')
        inactive_user.is_active = False
        inactive_user.save(update_fields=['is_active'])
        room = Room.objects.create(title='old-dm-active-old-dm-inactive', public=False)
        room.allowed.set([active_user, inactive_user])
        message = Message.objects.create(room=room, sender=active_user, text='Old direct message')
        old_time = timezone.now() - timedelta(days=400)
        Message.objects.filter(pk=message.pk).update(time=old_time)
        Room.objects.filter(pk=room.pk).update(last_activity=old_time)

        params = {'archive_public_chat_room': 9, 'delete_public_chat_room': 360, 'delete_inactive_user_after': 30}
        with patch('site_settings.params.get_param', side_effect=params.__getitem__):
            call_command('chat_rooms')

        self.assertFalse(Room.objects.filter(pk=room.pk).exists())

    def test_scheduler_does_not_unarchive_archived_source_document(self):
        post = PostFactory(title='Still archived', visibility='archive')
        params = {'archive_public_chat_room': 9, 'delete_public_chat_room': 360}

        with patch('site_settings.params.get_param', side_effect=params.__getitem__):
            call_command('chat_rooms')

        post.chat_room.refresh_from_db()
        post.refresh_from_db()
        self.assertTrue(post.chat_room.archived)
        self.assertEqual(post.visibility, 'archive')

    def test_old_unprotected_group_document_room_is_archived_not_deleted(self):
        active_user = make_user('source-room-active')
        inactive_user = make_user('source-room-inactive')
        inactive_user.is_active = False
        inactive_user.save(update_fields=['is_active'])
        room = Room.objects.create(title='Old group document', public=False, source_app='board', source_object_id=9001)
        room.allowed.set([active_user, inactive_user])
        message = Message.objects.create(room=room, sender=active_user, text='Old message')
        old_time = timezone.now() - timedelta(days=400)
        Message.objects.filter(pk=message.pk).update(time=old_time)
        Room.objects.filter(pk=room.pk).update(last_activity=old_time)

        params = {'archive_public_chat_room': 9, 'delete_public_chat_room': 360, 'delete_inactive_user_after': 30}
        with patch('site_settings.params.get_param', side_effect=params.__getitem__):
            call_command('chat_rooms')

        room.refresh_from_db()
        self.assertTrue(Room.objects.filter(pk=room.pk).exists())
        self.assertTrue(room.archived)
        self.assertEqual(room.messages.count(), 1)
        self.assertEqual(room.source_app, 'board')
        self.assertEqual(room.source_object_id, 9001)


class DiscussionRoomAuditCommandTest(TestCase):
    def test_duplicate_room_link_preflight_detects_cross_app_references(self):
        objects_by_app = {'board': [SimpleNamespace(pk=1, chat_room_id=8)], 'tasks': [SimpleNamespace(pk=2, chat_room_id=8)]}

        self.assertEqual(RepairDiscussionRoomsCommand._duplicate_room_links(objects_by_app), {8: ['board #1', 'tasks #2']})

    def test_duplicate_source_key_preflight_includes_unregistered_apps(self):
        room_keys = [(1, 'external', 42), (2, 'external', 42), (3, 'board', 7), (4, 'external', None)]

        self.assertEqual(RepairDiscussionRoomsCommand._duplicate_source_room_keys(room_keys), {('external', 42): [1, 2]})

    def test_scoped_audit_detects_cross_app_room_links_without_writing(self):
        post = PostFactory(title='Post linked from task')
        task = make_task()
        Task.objects.filter(pk=task.pk).update(chat_room_id=post.chat_room_id)
        output = StringIO()

        call_command('repair_discussion_rooms', '--audit', '--app', 'board', stdout=output)

        self.assertIn(f"Room #{post.chat_room_id} is linked to multiple source objects: ['board #{post.pk}', 'tasks #{task.pk}']", output.getvalue())
        task.refresh_from_db()
        self.assertEqual(task.chat_room_id, post.chat_room_id)
        self.assertIn('no data was changed', output.getvalue())

    def test_audit_reports_missing_source_metadata_without_writing(self):
        post = PostFactory(title='Legacy room without source metadata')
        room = post.chat_room
        Room.objects.filter(pk=room.pk).update(source_app='', source_object_id=None)
        output = StringIO()

        call_command('repair_discussion_rooms', '--audit', '--app', 'board', stdout=output)

        room.refresh_from_db()
        self.assertIn(f"board #{post.pk}: room #{room.pk} has source '' #None", output.getvalue())
        self.assertIn('no data was changed', output.getvalue())
        self.assertEqual(room.source_app, '')
        self.assertIsNone(room.source_object_id)

    def test_repair_requires_review_confirmation_and_is_idempotent(self):
        post = PostFactory(title='Legacy room for repair', visibility='group')
        room = post.chat_room
        Room.objects.filter(pk=room.pk).update(source_app='', source_object_id=None)
        room.allowed.clear()
        with self.assertRaises(CommandError):
            call_command('repair_discussion_rooms', '--repair-source-data', '--app', 'board', stdout=StringIO())

        output = StringIO()
        call_command('repair_discussion_rooms', '--repair-source-data', '--confirm-reviewed-backup', '--app', 'board', stdout=output)
        room.refresh_from_db()
        self.assertEqual(room.source_app, 'board')
        self.assertEqual(room.source_object_id, post.pk)
        self.assertTrue(room.allowed.filter(pk=post.author_id).exists())
        self.assertIn('Repaired 0 room link(s), 1 source marker(s)', output.getvalue())

        output = StringIO()
        call_command('repair_discussion_rooms', '--repair-source-data', '--confirm-reviewed-backup', '--app', 'board', stdout=output)
        self.assertIn('Repaired 0 room link(s), 0 source marker(s), and added 0 membership(s)', output.getvalue())

    def test_repair_does_not_create_a_room_for_an_ambiguous_legacy_title(self):
        post = PostFactory(title='Possible old-title match')
        room = post.chat_room
        Room.objects.filter(pk=room.pk).update(source_app='', source_object_id=None)
        post.__class__.objects.filter(pk=post.pk).update(chat_room=None)
        room_count = Room.objects.count()

        with self.assertRaises(CommandError):
            call_command('repair_discussion_rooms', '--repair-source-data', '--confirm-reviewed-backup', '--app', 'board', stdout=StringIO())

        post.refresh_from_db()
        self.assertIsNone(post.chat_room_id)
        self.assertEqual(Room.objects.count(), room_count)
        self.assertTrue(Room.objects.filter(pk=room.pk).exists())
