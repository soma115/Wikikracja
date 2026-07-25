from unittest.mock import AsyncMock, MagicMock, patch

from channels.db import database_sync_to_async
from django.test import TestCase

from chat.consumers import ChatConsumer
from chat.models import Room
from chat.tests.utils import make_user


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
        with patch.object(ChatConsumer.online_registry, 'get_online',
                          return_value=[self.receiver.id]):
            with patch.object(ChatConsumer.online_registry, 'get_consumer',
                              return_value=receiver_consumer):
                with patch('chat.consumers.asyncio.create_task') as mock_create_task:
                    await sender_consumer._post_send_processing(
                        self.sender, self.room, msg, message_id=1
                    )
                    return mock_create_task

    async def test_seen_receiver_gets_unseen_and_count_push(self):
        """Receiver had seen the room — repo.unsee_room and push_unread_count must be called."""
        await database_sync_to_async(self.room.seen_by.add)(self.receiver)
        sender = self._make_sender_consumer()
        receiver = self._make_receiver_consumer()

        mock_create_task = await self._run(sender, receiver)

        receiver.repo.unsee_room.assert_called_once_with(self.room)
        receiver.push_unread_count.assert_called_once()
        mock_create_task.assert_not_called()

    async def test_not_seen_receiver_skips_unseen_and_push(self):
        """Receiver had NOT seen the room — repo.unsee_room and push_unread_count must NOT be called."""
        # seen_by is empty — receiver not in it
        sender = self._make_sender_consumer()
        receiver = self._make_receiver_consumer()

        mock_create_task = await self._run(sender, receiver)

        receiver.repo.unsee_room.assert_not_called()
        receiver.push_unread_count.assert_not_called()
        mock_create_task.assert_not_called()

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

        mock_log.error.assert_not_called()   # bug: crash is swallowed into log.error
        mock_create_task.assert_not_called()  # muted → no push
