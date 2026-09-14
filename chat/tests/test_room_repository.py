from django.test import TestCase

from chat.exceptions import ClientError
from chat.models import Room
from chat.room_repository import ChatRoomRepository
from chat.tests.utils import make_user


class ChatRoomRepositoryTest(TestCase):
    def setUp(self):
        self.user = make_user('room-repository-user')
        self.other = make_user('room-repository-other')
        self.public_room = Room.objects.create(title='Public repository room', public=True)
        self.private_room = Room.objects.create(title='Private repository room', public=False)
        self.private_room.allowed.add(self.other)

    async def test_public_room_is_accessible(self):
        room = await ChatRoomRepository(self.user).get_room_or_error(self.public_room.id)
        self.assertEqual(room, self.public_room)

    async def test_private_room_denies_nonmember(self):
        with self.assertRaises(ClientError) as raised:
            await ChatRoomRepository(self.user).get_room_or_error(self.private_room.id)
        self.assertEqual(raised.exception.code, 'ACCESS_DENIED')
