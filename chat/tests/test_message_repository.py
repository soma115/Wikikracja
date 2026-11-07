from django.test import TestCase

from chat.exceptions import ClientError
from chat.message_repository import ChatMessageRepository
from chat.models import Message, MessageAttachment, Room
from chat.tests.utils import make_user


class ChatMessageRepositoryTest(TestCase):
    def setUp(self):
        self.user = make_user('message-repository-user')
        self.room = Room.objects.create(title='Message repository room')
        self.message = Message.objects.create(room=self.room, sender=self.user, text='Original')
        self.repository = ChatMessageRepository(self.user)

    async def test_message_operations_require_access_to_the_room(self):
        private_room = await Room.objects.acreate(title='Private message repository room', public=False)
        message = await Message.objects.acreate(room=private_room, sender=self.user, text='Private')

        with self.assertRaises(ClientError) as raised:
            await self.repository.get_message(message.id)

        self.assertEqual(raised.exception.code, 'ACCESS_DENIED')

    async def test_message_lookup_returns_message_and_room(self):
        message = await self.repository.get_message(self.message.id)
        room = await self.repository.get_room_by_message(self.message.id)

        self.assertEqual(message, self.message)
        self.assertEqual(room, self.room)

    async def test_get_user_by_id_returns_none_for_missing_ids(self):
        self.assertEqual(await self.repository.get_user_by_id(self.user.id), self.user)
        self.assertIsNone(await self.repository.get_user_by_id(None))
        self.assertIsNone(await self.repository.get_user_by_id(999999))

    async def test_edit_saves_previous_text_and_returns_history(self):
        state = await self.repository.edit_message_and_history(self.message.id, 'Updated')
        states = await self.repository.get_message_states(self.message.id)
        message = await Message.objects.aget(pk=self.message.id)

        self.assertEqual(state.text, 'Original')
        self.assertEqual(message.text, 'Updated')
        self.assertEqual([item['text'] for item in states], ['Original'])
        self.assertIsInstance(states[0]['timestamp'], int)

    async def test_attachment_operations_save_load_and_remove(self):
        await self.repository.save_attachments(self.message.id, {'images': ['first.webp', 'second.webp']})
        attachments = await self.repository.load_attachments(self.message.id)

        self.assertEqual(attachments, {'images': ['first.webp', 'second.webp']})

        await self.repository.remove_attachments(self.message.id, ['first.webp'])

        self.assertEqual(await self.repository.load_attachments(self.message.id), {'images': ['second.webp']})
        self.assertEqual(await MessageAttachment.objects.acount(), 1)

    async def test_is_last_message_in_room(self):
        self.assertTrue(await self.repository.is_last_message_in_room(self.message.id, self.room.id))
        await Message.objects.acreate(room=self.room, sender=self.user, text='Later')
        self.assertFalse(await self.repository.is_last_message_in_room(self.message.id, self.room.id))
