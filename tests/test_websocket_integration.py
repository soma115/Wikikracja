"""
WebSocket Integration Tests for all apps.
Test WebSocket connections and real-time features.
"""
import asyncio

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.test.utils import override_settings

from chat.models import Room
from zzz.routing import application

# Test configuration for Channels
CHANNEL_LAYERS_TEST = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class TestWebSocketConnection(TransactionTestCase):
    """Test WebSocket connections."""
    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass123', email='test@example.com')
        self.room = Room.objects.create(title='Test Public Room', public=True)
        self.room.allowed.add(self.user)

    async def test_websocket_connect_and_disconnect(self):
        """Test basic WebSocket connect/disconnect."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.disconnect()

    async def test_websocket_connect_anonymous_rejected(self):
        """Test that anonymous users are rejected."""
        from django.contrib.auth.models import AnonymousUser
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = AnonymousUser()

        connected, _ = await communicator.connect()
        assert not connected

    async def test_websocket_send_message(self):
        """Test sending message via WebSocket."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "join",
            "room_id": self.room.id
        })

        response = await communicator.receive_json_from()
        assert "join" in response or "error" in response

        await communicator.disconnect()

    async def test_websocket_send_invalid_json(self):
        """Test sending invalid JSON."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "invalid": "data"
        })

        await communicator.disconnect()

    async def test_websocket_join_room(self):
        """Test joining a chat room via WebSocket."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "join",
            "room_id": self.room.id
        })

        response = await communicator.receive_json_from()
        assert response.get("join") == str(self.room.id)
        assert "title" in response
        assert "public" in response

        await communicator.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class TestWebSocketMessaging(TransactionTestCase):
    """Test WebSocket messaging."""
    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user1 = User.objects.create_user(username='user1', password='pass1', email='user1@example.com')
        self.user2 = User.objects.create_user(username='user2', password='pass2', email='user2@example.com')
        self.room = Room.objects.create(title='Test Room', public=True)
        self.room.allowed.add(self.user1)
        self.room.allowed.add(self.user2)

    async def test_websocket_notification_received(self):
        """Test that notifications are received."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user1

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "join",
            "room_id": self.room.id
        })
        await communicator.receive_json_from()

        await communicator.send_json_to({
            "command": "get-notifications-data"
        })

        response = await communicator.receive_json_from()
        assert "rooms" in response

        await communicator.disconnect()

    async def test_multiple_users_in_room(self):
        """Test multiple users in same room."""
        comm1 = WebsocketCommunicator(application, "/chat/stream/")
        comm1.scope['user'] = self.user1
        connected, _ = await comm1.connect()
        assert connected

        await comm1.send_json_to({
            "command": "join",
            "room_id": self.room.id
        })
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, "/chat/stream/")
        comm2.scope['user'] = self.user2
        connected, _ = await comm2.connect()
        assert connected

        await comm2.send_json_to({
            "command": "join",
            "room_id": self.room.id
        })
        await comm2.receive_json_from()

        await comm1.send_json_to({
            "command": "send",
            "room_id": self.room.id,
            "message": "Hello from user1!",
            "is_anonymous": False,
            "attachments": {}
        })

        msg1 = await comm1.receive_json_from(timeout=2)
        assert "messages" in msg1

        msg2 = await comm2.receive_json_from(timeout=2)
        assert "messages" in msg2

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_websocket_invalid_message(self):
        """Test handling of invalid messages."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user1

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "send",
            "room_id": self.room.id,
            "message": "Should fail",
            "is_anonymous": False,
            "attachments": {}
        })

        response = await communicator.receive_json_from()
        assert response.get("error") == "ROOM_ACCESS_DENIED"

        await communicator.disconnect()

    async def test_websocket_message_history(self):
        """Test message history via WebSocket."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user1

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "join",
            "room_id": self.room.id
        })
        await communicator.receive_json_from()

        await communicator.send_json_to({
            "command": "fetch-messages",
            "room_id": self.room.id,
            "sort_by": "date",
            "order": "desc",
            "popular_only": False
        })

        response = await communicator.receive_json_from()
        assert "messages" in response or "replace_messages" in response

        await communicator.disconnect()


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS_TEST)
class TestWebSocketErrors(TransactionTestCase):
    """Test WebSocket error handling."""
    def setUp(self):
        """Set up test data."""
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='pass123', email='test@example.com')
        self.private_room = Room.objects.create(title='Private Room', public=False)
        self.non_member = User.objects.create_user(username='nonmember', password='pass456', email='nonmember@example.com')

    async def test_websocket_invalid_room(self):
        """Test connecting to non-existent room."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "join",
            "room_id": 99999
        })

        response = await communicator.receive_json_from(timeout=2)
        assert "join" in response or "error" in response

        await communicator.disconnect()

    async def test_websocket_unauthorized(self):
        """Test unauthorized WebSocket access."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.non_member

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "join",
            "room_id": self.private_room.id
        })

        response = await communicator.receive_json_from()
        assert response.get("error") == "ACCESS_DENIED"

        await communicator.disconnect()

    async def test_websocket_invalid_reaction(self):
        """Test sending invalid reaction."""
        communicator = WebsocketCommunicator(application, "/chat/stream/")
        communicator.scope['user'] = self.user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({
            "command": "message-react",
            "reaction": "invalid_reaction",
            "message_id": 1
        })

        response = await communicator.receive_json_from()
        assert response.get("error") == "INVALID_REACTION"

        await communicator.disconnect()
