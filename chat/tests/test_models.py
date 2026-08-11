from django.test import TestCase

from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
from chat.tests.utils import make_user


class RoomModelTest(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.public_room = Room.objects.create(title="Ogólny", public=True)
        self.public_room.allowed.set([self.alice, self.bob])
        self.private_room = Room.objects.create(title="alice-bob", public=False)
        self.private_room.allowed.set([self.alice, self.bob])

    def test_str_returns_title(self):
        self.assertEqual(str(self.public_room), "Ogólny")

    def test_group_name_format(self):
        self.assertEqual(self.public_room.group_name, f"room-{self.public_room.id}")

    def test_displayed_name_public_room(self):
        self.assertEqual(self.public_room.displayed_name(self.alice), "Ogólny")

    def test_displayed_name_public_room_clips_long_title(self):
        long_title = "A" * 100
        room = Room.objects.create(title=long_title, public=True)
        self.assertEqual(len(room.displayed_name(self.alice)), 90)

    def test_displayed_name_private_room_shows_other_user(self):
        self.assertEqual(self.private_room.displayed_name(self.alice), "bob")

    def test_displayed_name_private_room_no_other_user_returns_placeholder(self):
        solo_room = Room.objects.create(title="solo", public=False)
        solo_room.allowed.set([self.alice])
        self.assertEqual(solo_room.displayed_name(self.alice), "--")

    def test_get_other_returns_counterpart(self):
        self.assertEqual(self.private_room.get_other(self.alice), self.bob)

    def test_find_with_users_finds_private_room(self):
        self.assertEqual(Room.find_with_users(self.alice, self.bob), self.private_room)

    def test_find_with_users_returns_none_when_no_room(self):
        charlie = make_user("charlie")
        self.assertIsNone(Room.find_with_users(self.alice, charlie))

    def test_find_private_rooms_for_user_pairs_returns_mapping(self):
        result = Room.find_private_rooms_for_user_pairs(self.alice, [self.bob.id])
        self.assertEqual(result[self.bob.id], self.private_room)

    def test_find_private_rooms_for_user_pairs_empty_list(self):
        self.assertEqual(Room.find_private_rooms_for_user_pairs(self.alice, []), {})

    def test_get_members_excluding_excludes_user(self):
        members = Room.get_members_excluding(self.public_room.id, self.alice.id)
        self.assertNotIn(self.alice, members)
        self.assertIn(self.bob, members)

    def test_get_members_excluding_nonexistent_room(self):
        self.assertEqual(list(Room.get_members_excluding(99999, self.alice.id)), [])

    def test_get_membership_preferences_bulk_defaults(self):
        result = Room.get_membership_preferences_bulk(self.public_room.id, [self.alice.id])
        self.assertFalse(result[self.alice.id]["seen"])
        self.assertFalse(result[self.alice.id]["muted"])

    def test_get_membership_preferences_bulk_seen(self):
        self.public_room.seen_by.add(self.alice)
        result = Room.get_membership_preferences_bulk(self.public_room.id, [self.alice.id])
        self.assertTrue(result[self.alice.id]["seen"])

    def test_get_membership_preferences_bulk_muted(self):
        self.public_room.muted_by.add(self.alice)
        result = Room.get_membership_preferences_bulk(self.public_room.id, [self.alice.id])
        self.assertTrue(result[self.alice.id]["muted"])

    def test_get_membership_preferences_bulk_empty_user_ids(self):
        self.assertEqual(Room.get_membership_preferences_bulk(self.public_room.id, []), {})


class MessageModelTest(TestCase):
    def setUp(self):
        self.user = make_user("sender")
        self.room = Room.objects.create(title="TestRoom", public=True)
        self.room.allowed.add(self.user)
        self.msg = Message.objects.create(sender=self.user, room=self.room, text="Hello")

    def test_message_saved_with_correct_text(self):
        self.assertEqual(self.msg.text, "Hello")

    def test_message_anonymous_default_false(self):
        self.assertFalse(self.msg.anonymous)

    def test_message_reply_to_null_by_default(self):
        self.assertIsNone(self.msg.reply_to)

    def test_reply_to_links_messages(self):
        reply = Message.objects.create(sender=self.user, room=self.room, text="Reply", reply_to=self.msg)
        self.assertEqual(reply.reply_to, self.msg)

    def test_sender_set_null_on_user_delete(self):
        temp_user = make_user("temp")
        msg = Message.objects.create(sender=temp_user, room=self.room, text="bye")
        temp_user.delete()
        msg.refresh_from_db()
        self.assertIsNone(msg.sender)


class MessageReadByTest(TestCase):
    def setUp(self):
        self.user = make_user("reader")
        self.room = Room.objects.create(title="ReadRoom", public=True)
        self.msg = Message.objects.create(sender=self.user, room=self.room, text="Read me")

    def test_read_by_created(self):
        rb = MessageReadBy.objects.create(message=self.msg, user=self.user)
        self.assertEqual(rb.message, self.msg)

    def test_unique_constraint_read_twice(self):
        from django.db import IntegrityError

        MessageReadBy.objects.create(message=self.msg, user=self.user)
        with self.assertRaises(IntegrityError):
            MessageReadBy.objects.create(message=self.msg, user=self.user)


class MessageHistoryTest(TestCase):
    def setUp(self):
        self.user = make_user("editor")
        self.room = Room.objects.create(title="HistRoom", public=True)
        self.msg = Message.objects.create(sender=self.user, room=self.room, text="Original")

    def test_history_entry_stores_old_text(self):
        history = MessageHistory.objects.create(message=self.msg)
        entry = MessageHistoryEntry.objects.create(history=history, text="Original")
        self.assertEqual(entry.text, "Original")

    def test_multiple_history_entries(self):
        history = MessageHistory.objects.create(message=self.msg)
        MessageHistoryEntry.objects.create(history=history, text="v1")
        MessageHistoryEntry.objects.create(history=history, text="v2")
        self.assertEqual(history.entries.count(), 2)

    def test_history_deleted_with_message(self):
        history = MessageHistory.objects.create(message=self.msg)
        MessageHistoryEntry.objects.create(history=history, text="v1")
        self.msg.delete()
        self.assertFalse(MessageHistory.objects.filter(id=history.id).exists())


class RoomLastMessageSignalTest(TestCase):
    """Signal post_save(Message) → Room.last_message_* sync."""

    def setUp(self):
        self.user = make_user("signaluser")
        self.room = Room.objects.create(title="SignalRoom", public=True)
        self.room.allowed.add(self.user)

    def test_creating_message_updates_last_message_at(self):
        self.assertIsNone(self.room.last_message_at)
        msg = Message.objects.create(sender=self.user, room=self.room, text="Hi")
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_message_at, msg.time)

    def test_creating_message_unarchives_room(self):
        self.room.archived = True
        self.room.save(update_fields=['archived'])
        Message.objects.create(sender=self.user, room=self.room, text="Hi")
        self.room.refresh_from_db()
        self.assertFalse(self.room.archived)

    def test_creating_message_updates_last_message_text(self):
        Message.objects.create(sender=self.user, room=self.room, text="Hello world")
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_message_text, "Hello world")

    def test_creating_message_updates_last_message_sender(self):
        Message.objects.create(sender=self.user, room=self.room, text="Hi")
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_message_sender_id, self.user.id)

    def test_creating_anonymous_message_sets_anonymous_flag(self):
        Message.objects.create(sender=None, room=self.room, text="Anon", anonymous=True)
        self.room.refresh_from_db()
        self.assertTrue(self.room.last_message_anonymous)

    def test_long_message_text_truncated_to_200_chars(self):
        Message.objects.create(sender=self.user, room=self.room, text="A" * 300)
        self.room.refresh_from_db()
        self.assertEqual(len(self.room.last_message_text), 200)

    def test_other_rooms_unaffected_by_message_in_one_room(self):
        other_room = Room.objects.create(title="OtherSignalRoom", public=True)
        Message.objects.create(sender=self.user, room=self.room, text="Hi")
        other_room.refresh_from_db()
        self.assertIsNone(other_room.last_message_at)
        self.assertEqual(other_room.last_message_text, '')

    def test_message_does_not_move_last_activity_backwards(self):
        from datetime import timedelta

        from django.utils import timezone

        future = timezone.now() + timedelta(hours=1)
        Room.objects.filter(id=self.room.id).update(last_activity=future)
        Message.objects.create(sender=self.user, room=self.room, text="Hi")
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_activity, future)

    def test_editing_last_message_updates_last_message_text(self):
        msg = Message.objects.create(sender=self.user, room=self.room, text="Original")
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_message_text, "Original")

        msg.text = "Edited"
        msg.save(update_fields=['text'])
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_message_text, "Edited")

    def test_editing_non_last_message_does_not_update_last_message_text(self):
        first = Message.objects.create(sender=self.user, room=self.room, text="First")
        Message.objects.create(sender=self.user, room=self.room, text="Second")
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_message_text, "Second")

        first.text = "First-edited"
        first.save(update_fields=['text'])
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_message_text, "Second")


class MessageAttachmentTest(TestCase):
    def setUp(self):
        self.user = make_user("uploader")
        self.room = Room.objects.create(title="AttachRoom", public=True)
        self.msg = Message.objects.create(sender=self.user, room=self.room, text="See file")

    def test_attachment_created(self):
        att = MessageAttachment.objects.create(type="image/png", filename="photo.png", message=self.msg)
        self.assertEqual(att.filename, "photo.png")
        self.assertEqual(att.message, self.msg)

    def test_attachment_deleted_with_message(self):
        att = MessageAttachment.objects.create(type="image/png", filename="photo.png", message=self.msg)
        att_id = att.id
        self.msg.delete()
        self.assertFalse(MessageAttachment.objects.filter(id=att_id).exists())
