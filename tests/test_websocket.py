"""Testy integracyjne WebSocket dla ChatConsumer.

Pokrywają: rejekcję anonymous, sukces auth, join public/private, send w/bez join,
multi-user broadcast, invalid reaction, get-notifications-data.
"""

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser

from chat.models import Message, Room
from tests.factories import UserFactory
from zzz.routing import application


async def _consume_initial(communicator):
    """Po connect ChatConsumer wysyła {unread_count}. Zjadamy żeby kolejne receive zwracało odpowiedź na nasze polecenie."""
    await communicator.receive_json_from()


@pytest.fixture
def public_room_with_user(db):
    user = UserFactory(username='wsuser', email='ws@example.com')
    room = Room.objects.create(title='WS Public Room', public=True)
    return user, room


@pytest.fixture
def private_room_with_users(db):
    member = UserFactory(username='wsmember', email='member@example.com')
    nonmember = UserFactory(username='wsnonmember', email='nonmember@example.com')
    room = Room.objects.create(title='WS Private Room', public=False, protected=False)
    room.allowed.add(member)
    return member, nonmember, room


@pytest.mark.django_db(transaction=True)
async def test_anonymous_user_rejected():
    """Anonymous user nie może otworzyć WS — connect zwraca False."""
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = AnonymousUser()
    connected, _ = await communicator.connect()
    assert connected is False


@pytest.mark.django_db(transaction=True)
async def test_authenticated_user_receives_unread_count(public_room_with_user):
    """Auth user po connect dostaje {unread_count: N} jako pierwszą wiadomość."""
    user, _ = public_room_with_user
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = user
    connected, _ = await communicator.connect()
    assert connected is True

    response = await communicator.receive_json_from()
    assert 'unread_count' in response
    assert isinstance(response['unread_count'], int)

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_join_public_room_returns_metadata(public_room_with_user):
    """Join public room zwraca {join: room_id, title, public, notifications}."""
    user, room = public_room_with_user
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = user
    connected, _ = await communicator.connect()
    assert connected is True
    await _consume_initial(communicator)

    await communicator.send_json_to({"command": "join", "room_id": room.id})
    response = await communicator.receive_json_from()

    assert response.get('join') == str(room.id)
    assert response.get('title') == 'WS Public Room'
    assert response.get('public') is True
    assert 'notifications' in response

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_join_private_room_as_nonmember_denied(private_room_with_users):
    """Nie-członek próbujący wejść do private room dostaje {error: ACCESS_DENIED}."""
    _member, nonmember, room = private_room_with_users
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = nonmember
    connected, _ = await communicator.connect()
    assert connected is True
    await _consume_initial(communicator)

    await communicator.send_json_to({"command": "join", "room_id": room.id})
    response = await communicator.receive_json_from()

    assert response.get('error') == 'ACCESS_DENIED'

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_private_message_commands_as_nonmember_are_denied(private_room_with_users):
    member, nonmember, room = private_room_with_users
    message = await sync_to_async(Message.objects.create)(sender=member, text='Private', room=room)
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = nonmember
    connected, _ = await communicator.connect()
    assert connected is True
    await _consume_initial(communicator)

    for command in (
        {"command": "get-message-history", "message_id": message.id},
        {"command": "message-react", "reaction": "bulb", "message_id": message.id},
        {"command": "message-add-vote", "vote": "upvote", "message_id": message.id},
        {"command": "message-mark-read", "message_id": message.id},
        {"command": "messages-mark-read-bulk", "message_ids": [message.id], "room_id": room.id},
        {"command": "toggle-notifications", "room_id": room.id, "enabled": False},
    ):
        await communicator.send_json_to(command)
        response = await communicator.receive_json_from()
        assert response.get('error') == 'ACCESS_DENIED'

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_reply_to_message_from_another_room_is_denied(public_room_with_user, private_room_with_users):
    user, public_room = public_room_with_user
    member, _nonmember, private_room = private_room_with_users
    private_message = await sync_to_async(Message.objects.create)(sender=member, text='Private', room=private_room)
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = user
    connected, _ = await communicator.connect()
    assert connected is True
    await _consume_initial(communicator)

    await communicator.send_json_to({"command": "join", "room_id": public_room.id})
    await communicator.receive_json_from()
    await communicator.send_json_to({"command": "send", "room_id": public_room.id, "message": "Reply", "is_anonymous": False, "attachments": {}, "reply_to_id": private_message.id})
    response = await communicator.receive_json_from()

    assert response.get('error') == 'ACCESS_DENIED'
    assert not await sync_to_async(Message.objects.filter(room=public_room, text='Reply').exists)()
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_send_to_unjoined_room_denied(public_room_with_user):
    """Send do pokoju bez wcześniejszego join dostaje {error: ROOM_ACCESS_DENIED}."""
    user, room = public_room_with_user
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = user
    connected, _ = await communicator.connect()
    assert connected is True
    await _consume_initial(communicator)

    await communicator.send_json_to({"command": "send", "room_id": room.id, "message": "Hello", "is_anonymous": False, "attachments": {}})
    response = await communicator.receive_json_from()

    assert response.get('error') == 'ROOM_ACCESS_DENIED'

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_invalid_reaction_rejected(public_room_with_user):
    """message-react z nieprawidłową reakcją dostaje {error: INVALID_REACTION}."""
    user, room = public_room_with_user
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = user
    connected, _ = await communicator.connect()
    assert connected is True
    await _consume_initial(communicator)

    from chat.models import Message

    message = await sync_to_async(Message.objects.create)(sender=user, text='Test', room=room, anonymous=False)

    await communicator.send_json_to({"command": "message-react", "reaction": "invalid_reaction_xyz", "message_id": message.id})
    response = await communicator.receive_json_from()

    assert response.get('error') == 'INVALID_REACTION'

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_get_notifications_data_returns_rooms(public_room_with_user):
    """Komenda get-notifications-data zwraca odpowiedź z polem 'rooms'."""
    user, _ = public_room_with_user
    communicator = WebsocketCommunicator(application, "/chat/stream/")
    communicator.scope['user'] = user
    connected, _ = await communicator.connect()
    assert connected is True
    await _consume_initial(communicator)

    await communicator.send_json_to({"command": "get-notifications-data"})
    response = await communicator.receive_json_from()

    assert 'rooms' in response

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_multi_user_broadcast(private_room_with_users):
    """Wiadomość od user1 dociera przez channel layer do user2 obecnego w tym samym pokoju."""
    member, nonmember, room = private_room_with_users
    await sync_to_async(room.allowed.add)(nonmember)

    comm1 = WebsocketCommunicator(application, "/chat/stream/")
    comm1.scope['user'] = member
    connected, _ = await comm1.connect()
    assert connected is True
    await _consume_initial(comm1)

    comm2 = WebsocketCommunicator(application, "/chat/stream/")
    comm2.scope['user'] = nonmember
    connected, _ = await comm2.connect()
    assert connected is True
    await _consume_initial(comm2)

    await comm1.send_json_to({"command": "join", "room_id": room.id})
    await comm1.receive_json_from()
    await comm2.send_json_to({"command": "join", "room_id": room.id})
    await comm2.receive_json_from()

    await comm1.send_json_to({"command": "send", "room_id": room.id, "message": "Hello from member", "is_anonymous": False, "attachments": {}})

    # User2 może dostać kilka różnych eventów (online_data, unread_count update) przed właściwą wiadomością.
    # Czytamy do skutku (max 10 wiadomości / timeout 1s każda) i szukamy konkretnej treści.
    found = False
    for _ in range(10):
        try:
            response = await comm2.receive_json_from(timeout=1)
        except Exception:
            break
        if 'Hello from member' in str(response):
            found = True
            break

    assert found, "User2 nie otrzymał broadcast'u 'Hello from member' od user1"

    await comm1.disconnect()
    await comm2.disconnect()
