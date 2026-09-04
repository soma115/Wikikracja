from unittest.mock import AsyncMock, MagicMock, patch

from channels.db import database_sync_to_async
from django.test import TestCase

from chat.consumers import ChatConsumer
from chat.models import Message, Room
from chat.tests.utils import make_user
from chat.utils import HandledMessage
from tasks.tests.utils import make_task


class PostSendProcessingUnseenTest(TestCase):
    """
    Regression tests for _post_send_processing: ensures the correct call path
    consumer.repo.unsee_room(room) is used (not the non-existent consumer.unsee_room),
    and that push_unread_count is called iff the receiver had previously seen the room.
    """

    def setUp(self):
        self.sender = make_user("sender")
        self.receiver = make_user("receiver")
        self.room = Room.objects.create(title="test-room", public=False)
        self.room.allowed.add(self.sender, self.receiver)

    def _make_sender_consumer(self):
        consumer = ChatConsumer.__new__(ChatConsumer)
        consumer.scope = {'user': self.sender}
        consumer.channel_layer = AsyncMock()
        consumer.send_push_notification_async = MagicMock(return_value=None)
        return consumer

    def _make_receiver_consumer(self):
        consumer = MagicMock(spec=ChatConsumer)
        consumer.scope = {'user': self.receiver}
        consumer.rooms = MagicMock()
        consumer.rooms.present = MagicMock(return_value=False)
        consumer.repo = AsyncMock()
        consumer.repo.unsee_room = AsyncMock()
        consumer.send_unsee_room = AsyncMock()
        consumer.push_unread_count = AsyncMock()
        return consumer

    async def _run(self, sender_consumer, receiver_consumer):
        msg = MagicMock()
        msg.time = None
        with patch.object(ChatConsumer.online_registry, 'get_online', return_value=[self.receiver.id]):
            with patch.object(ChatConsumer.online_registry, 'get_consumer', return_value=receiver_consumer):
                with patch('chat.consumers.asyncio.create_task') as mock_create_task:
                    await sender_consumer._post_send_processing(self.sender, self.room, msg, message_id=1)
                    return mock_create_task

    async def test_seen_receiver_gets_unseen_count_and_push(self):
        """Receiver had seen the room — repo.unsee_room, push_unread_count and push task must be called."""
        await database_sync_to_async(self.room.seen_by.add)(self.receiver)
        sender = self._make_sender_consumer()
        receiver = self._make_receiver_consumer()

        mock_create_task = await self._run(sender, receiver)

        receiver.repo.unsee_room.assert_called_once_with(self.room)
        receiver.push_unread_count.assert_called_once()
        mock_create_task.assert_called_once()

    async def test_not_seen_receiver_skips_unseen_and_count_but_pushes(self):
        """Receiver had NOT seen the room — repo.unsee_room and push_unread_count must NOT be called, but push is still sent."""
        # seen_by is empty — receiver not in it
        sender = self._make_sender_consumer()
        receiver = self._make_receiver_consumer()

        mock_create_task = await self._run(sender, receiver)

        receiver.repo.unsee_room.assert_not_called()
        receiver.push_unread_count.assert_not_called()
        mock_create_task.assert_called_once()

    async def test_race_no_consumer_muted_seen_does_not_crash(self):
        """Regression: race condition where online_registry reports member as online
        but get_consumer() returns None (e.g. disconnect between registry check and lookup),
        with muted=True and seen=True. Must not reach consumer.repo (None → AttributeError).
        No push (muted), no crash."""
        await database_sync_to_async(self.room.seen_by.add)(self.receiver)
        await database_sync_to_async(self.room.muted_by.add)(self.receiver)
        sender = self._make_sender_consumer()

        with patch('chat.consumers.log') as mock_log:
            mock_create_task = await self._run(sender, None)  # get_consumer → None

        mock_log.error.assert_not_called()  # bug: crash is swallowed into log.error
        mock_create_task.assert_not_called()  # muted → no push


class MentionNotificationTest(TestCase):
    """Regression tests for _send_mention_notification: room.name crash and room_name value."""

    def setUp(self):
        self.sender = make_user("alice")
        self.receiver = make_user("bob")
        self.room = Room.objects.create(title="alice-bob", public=False)
        self.room.allowed.set([self.sender, self.receiver])

    async def test_send_mention_notification_private_room_uses_sender_username(self):
        """Mention notification for a private room must use the sender's username as room name."""
        consumer = ChatConsumer.__new__(ChatConsumer)
        consumer.channel_layer = AsyncMock()
        with patch.object(ChatConsumer, 'repo', new=AsyncMock()):
            msg = MagicMock()
            msg.id = 7
            msg.anonymous = False

            await consumer._send_mention_notification(self.sender, self.room, self.receiver, msg)

            consumer.channel_layer.group_send.assert_awaited_once()
            group, payload = consumer.channel_layer.group_send.call_args.args
            self.assertEqual(group, f"user_{self.receiver.id}")
            self.assertEqual(payload["type"], "chat.mention")
            self.assertEqual(payload["room_id"], self.room.id)
            self.assertEqual(payload["notification"]["room_id"], self.room.id)
            self.assertIn(f"#room_id={self.room.id}", payload["notification"]["click_action"])

            consumer.repo.send_push_notification_sync.assert_awaited_once()
            call_args = consumer.repo.send_push_notification_sync.call_args
            self.assertEqual(call_args.args[0], self.receiver)
            self.assertEqual(call_args.kwargs.get("room_name"), self.sender.username)


class BroadcastVoteUpdateTest(TestCase):
    """update_votes w pokojach zadań zawiera nicki głosujących; w innych pokojach nie."""

    def setUp(self):
        self.voter = make_user("voter")
        self.task = make_task(created_by=self.voter)
        self.task_room = self.task.chat_room
        self.plain_room = Room.objects.create(title="plain-room", public=True)

        self.msg_task = Message.objects.create(room=self.task_room, sender=self.voter, text="x")
        self.msg_task.reactions = {'upvotes': [self.voter.id]}
        self.msg_task.save(update_fields=['reactions'])

        self.msg_plain = Message.objects.create(room=self.plain_room, sender=self.voter, text="x")
        self.msg_plain.reactions = {'upvotes': [self.voter.id]}
        self.msg_plain.save(update_fields=['reactions'])

    def _consumer(self):
        consumer = ChatConsumer.__new__(ChatConsumer)
        consumer.scope = {'user': self.voter}
        return consumer

    async def test_task_room_includes_voter_names(self):
        proxy = HandledMessage()
        await self._consumer()._broadcast_vote_update(proxy, self.msg_task.id, 'upvote', 1, 0, True)
        group, message = proxy.get_messages()[0][:2]
        self.assertEqual(group, self.task_room.group_name)
        self.assertEqual(message['update_votes']['upvoters'], ['voter'])
        self.assertEqual(message['update_votes']['downvoters'], [])

    async def test_plain_room_omits_voter_names(self):
        proxy = HandledMessage()
        await self._consumer()._broadcast_vote_update(proxy, self.msg_plain.id, 'upvote', 1, 0, True)
        group, message = proxy.get_messages()[0][:2]
        self.assertEqual(group, self.plain_room.group_name)
        self.assertNotIn('upvoters', message['update_votes'])
        self.assertNotIn('downvoters', message['update_votes'])


class HandledMessageSendAllTest(TestCase):
    """Regression tests for HandledMessage.send_all: it must dispatch all queued messages,
    not stop after the first one."""

    async def test_send_all_dispatches_group_consumer_and_self_messages(self):
        """A proxy with a group broadcast, a per-consumer message and a self message must send all three."""
        consumer = MagicMock()
        consumer.channel_layer = AsyncMock()
        consumer.send_json = AsyncMock()

        other_consumer = MagicMock()
        other_consumer.send_json = AsyncMock()

        proxy = HandledMessage()
        proxy.group_send('room_1', {'type': 'chat.message', 'text': 'broadcast'})
        proxy.send_json({'text': 'to_other'}, to_consumer=other_consumer)
        proxy.send_json({'text': 'to_self'})

        await proxy.send_all(consumer)

        consumer.channel_layer.group_send.assert_awaited_once_with('room_1', {'type': 'chat.message', 'text': 'broadcast'})
        other_consumer.send_json.assert_awaited_once_with({'text': 'to_other'})
        consumer.send_json.assert_awaited_once_with({'text': 'to_self'})
