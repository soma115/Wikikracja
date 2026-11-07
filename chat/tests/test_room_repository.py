from unittest.mock import patch

from django.test import TestCase

from chat.exceptions import ClientError
from chat.models import Message, MessageReadBy, Room
from chat.room_repository import CHAT_UNREAD_CACHE_KEY, ChatRoomRepository
from chat.tests.utils import make_user


class ChatRoomRepositoryTest(TestCase):
    def setUp(self):
        self.user = make_user('room-repository-user')
        self.other = make_user('room-repository-other')
        self.public_room = Room.objects.create(title='Public repository room', public=True)
        self.private_room = Room.objects.create(title='Private repository room', public=False)
        self.private_room.allowed.add(self.other)
        self.repository = ChatRoomRepository(self.user)

    async def test_public_room_is_accessible(self):
        room = await ChatRoomRepository(self.user).get_room_or_error(self.public_room.id)
        self.assertEqual(room, self.public_room)

    async def test_private_room_denies_nonmember(self):
        with self.assertRaises(ClientError) as raised:
            await self.repository.get_room_or_error(self.private_room.id)
        self.assertEqual(raised.exception.code, 'ACCESS_DENIED')

    async def test_mark_message_read_creates_receipt_and_invalidates_cache(self):
        message = await Message.objects.acreate(room=self.public_room, sender=self.other, text='Unread')

        with patch('chat.room_repository.cache.delete') as invalidate_cache:
            await self.repository.mark_message_read(message.id)

        self.assertTrue(await MessageReadBy.objects.filter(message=message, user=self.user).aexists())
        invalidate_cache.assert_called_once_with(CHAT_UNREAD_CACHE_KEY.format(user_id=self.user.id))

    async def test_bulk_read_returns_only_new_receipts(self):
        first = await Message.objects.acreate(room=self.public_room, sender=self.other, text='First')
        second = await Message.objects.acreate(room=self.public_room, sender=self.other, text='Second')

        with patch('chat.room_repository.cache.delete') as invalidate_cache:
            new_ids = await self.repository.mark_messages_read_bulk([str(first.id), second.id], self.public_room.id)
            repeated_ids = await self.repository.mark_messages_read_bulk([first.id, second.id], self.public_room.id)

        self.assertEqual(set(new_ids), {first.id, second.id})
        self.assertEqual(repeated_ids, [])
        self.assertEqual(await MessageReadBy.objects.filter(message__in=[first, second], user=self.user).acount(), 2)
        invalidate_cache.assert_called_once_with(CHAT_UNREAD_CACHE_KEY.format(user_id=self.user.id))

    async def test_bulk_read_rejects_message_from_another_room(self):
        message = await Message.objects.acreate(room=self.private_room, sender=self.other, text='Private')

        with self.assertRaises(ClientError) as raised:
            await self.repository.mark_messages_read_bulk([message.id], self.public_room.id)

        self.assertEqual(raised.exception.code, 'ACCESS_DENIED')

    async def test_get_read_by_data_returns_reader_payload(self):
        message = await Message.objects.acreate(room=self.public_room, sender=self.other, text='Unread')
        await self.repository.mark_message_read(message.id)

        readers = await self.repository.get_read_by_data(message.id)

        self.assertEqual(len(readers), 1)
        self.assertEqual(readers[0]['user_id'], self.user.id)
        self.assertEqual(readers[0]['username'], self.user.username)
