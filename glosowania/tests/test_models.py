# Standard library imports
from unittest.mock import patch

# Third party imports
from django.contrib.auth.models import User
from django.test import TestCase

# Local folder imports
from chat.models import Room
from glosowania.models import Decyzja


class DecyzjaChatRoomTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(username="author", password="x")

    def test_decyzja_creation_creates_chat_room(self):
        decyzja = Decyzja.objects.create(author=self.author, title="Test Bill", tresc="Test law text", status=Decyzja.Status.PROPOSITION)
        decyzja.refresh_from_db()
        self.assertIsNotNone(decyzja.chat_room)
        self.assertTrue(Room.objects.filter(title=decyzja.get_chat_room_title()).exists())
        self.assertEqual(decyzja.chat_room.title, decyzja.get_chat_room_title())

    def test_decyzja_not_saved_when_chat_room_creation_fails(self):
        with patch("chat.signals.Room.objects.create", side_effect=RuntimeError("DB unavailable")):
            with self.assertRaises(RuntimeError):
                Decyzja.objects.create(author=self.author, title="Test Bill", tresc="Test law text", status=Decyzja.Status.PROPOSITION)
        self.assertEqual(Decyzja.objects.count(), 0)
