"""Smoke test fundamentów: weryfikuje że factories + conftest działają."""
import pytest

from glosowania.models import Decyzja
from tests.factories import DecyzjaFactory, PostFactory, RoomFactory, UserFactory


@pytest.mark.django_db
def test_user_factory_creates_user():
    user = UserFactory()
    assert user.id is not None
    assert '@example.com' in user.email


@pytest.mark.django_db
def test_post_factory_with_relations():
    post = PostFactory()
    assert post.id is not None
    assert post.author is not None
    assert post.category is not None
    assert post.is_public is True


@pytest.mark.django_db
def test_room_factory():
    room = RoomFactory()
    assert room.id is not None
    assert room.public is True
    assert room.archived is False


@pytest.mark.django_db
def test_decyzja_factory_with_chat_room():
    decyzja = DecyzjaFactory()
    assert decyzja.id is not None
    assert decyzja.chat_room is not None
    assert decyzja.author is not None
    assert decyzja.status == Decyzja.Status.PROPOSITION


@pytest.mark.django_db
def test_authenticated_client_fixture(authenticated_client):
    client, user = authenticated_client
    assert user.email == 'test@example.com'
    assert user.id is not None


@pytest.mark.django_db
def test_chat_room_fixture(chat_room):
    room, users = chat_room
    assert room.title == 'TestRoom'
    assert room.public is False
    assert len(users) == 3
    assert room.allowed.count() == 3
