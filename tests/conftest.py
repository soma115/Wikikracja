"""
Shared fixtures for integration tests.
"""
import pytest


@pytest.fixture
def api_client():
    """Return Django test client."""
    from django.test import Client
    return Client()


@pytest.fixture
def authenticated_client(db):
    """Return authenticated client."""
    from django.contrib.auth import get_user_model
    from django.test import Client
    User = get_user_model()
    user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')
    client = Client()
    client.login(username='testuser', password='testpass123')
    return client, user


@pytest.fixture
def chat_room(db):
    """Create a test chat room with allowed users."""
    from django.contrib.auth import get_user_model

    from chat.models import Room
    User = get_user_model()

    # Create users
    users = []
    for i in range(3):
        user = User.objects.create_user(username='chatuser{i}'.format(i=i), email='chat{i}@example.com'.format(i=i), password='testpass123')
        users.append(user)

    # Create room
    room = Room.objects.create(title='TestRoom', public=False, archived=False, protected=False)
    room.allowed.add(*users)

    return room, users


@pytest.fixture
def board_category(db):
    """Create a board category."""
    from board.models import PostCategory
    return PostCategory.objects.create(name='Test Category', priority=1)


@pytest.fixture
def bookkeeping_category(db):
    """Create a bookkeeping category."""
    from bookkeeping.models import Category
    return Category.objects.create(name='Test Category')


@pytest.fixture
def bookkeeping_partner(db):
    """Create a bookkeeping partner."""
    from bookkeeping.models import Partner
    return Partner.objects.create(name='Test Partner', email='partner@example.com', phone='+48123456789', city='Warsaw', country='Poland')


@pytest.fixture
def glosowania_decyzja(db, chat_room):
    """Create a voting decision."""
    from glosowania.models import Decyzja
    room, users = chat_room
    return Decyzja.objects.create(title='Test Bill: Test law', tresc='Law text', kara='Penalty', author=users[0], chat_room=room)


@pytest.fixture
def sample_users(db):
    """Create sample users for testing."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = []
    for i in range(5):
        user = User.objects.create_user(username='sampleuser{i}'.format(i=i), email='sample{i}@example.com'.format(i=i), password='testpass123')
        users.append(user)
    return users
