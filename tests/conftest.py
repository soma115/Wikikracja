"""Wspólne fixtures dla testów cross-cutting w katalogu /tests/."""

import pytest
from django.test import Client

from tests.factories import UserFactory


@pytest.fixture
def authenticated_client(db):
    """Klient zalogowany przez force_login (omija backend auth — działa z allauth email-only)."""
    user = UserFactory(username='testuser', email='test@example.com')
    client = Client()
    client.force_login(user)
    return client, user


@pytest.fixture
def chat_room(db):
    """Pokój chatu prywatny z 3 dozwolonymi userami."""
    from chat.models import Room

    users = UserFactory.create_batch(3)
    room = Room.objects.create(title='TestRoom', public=False, archived=False, protected=False)
    room.allowed.add(*users)
    return room, users


@pytest.fixture
def board_category(db):
    from board.models import PostCategory

    return PostCategory.objects.create(name='Test Category', priority=1)


@pytest.fixture
def bookkeeping_category(db):
    from bookkeeping.models import Category

    return Category.objects.create(name='Test BK Category')


@pytest.fixture
def bookkeeping_partner(db):
    from bookkeeping.models import Partner

    return Partner.objects.create(name='Test Partner', email='partner@example.com', phone='+48123456789', city='Warsaw', country='Poland')


@pytest.fixture
def sample_users(db):
    """5 testowych userów."""
    return UserFactory.create_batch(5)
