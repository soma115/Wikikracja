"""
Pytest tests that create 100+ records per model using actual Django ORM logic.
Uses send_message_to_room for chat messages where possible.

Run with: pytest tests/test_models_pytest.py -v
"""
import random
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


@pytest.fixture
def users(db):
    """Create 20 test users."""
    users = []
    for i in range(1, 21):
        username = 'user{}'.format(i)
        email = 'user{}@example.com'.format(i)
        user, _ = User.objects.get_or_create(username=username, defaults={
            'email': email
        })
        users.append(user)
    return users


@pytest.fixture
def board_data(db, users):
    """Create board models: 100 categories + 100 posts."""
    from board.models import Post, PostCategory

    categories = []
    for i in range(1, 101):
        name = 'Category{}'.format(i)
        cat, _ = PostCategory.objects.get_or_create(name=name, defaults={
            'priority': i % 10 + 1
        })
        categories.append(cat)

    for i in range(1, 101):
        title = 'Article {}'.format(i)
        subtitle = 'Subtitle {}'.format(i)
        text = '<p>Content of article {}</p>'.format(i)
        Post.objects.create(
            title=title,
            subtitle=subtitle,
            text=text,
            author=random.choice(users),
            category=random.choice(categories),
            is_public=random.choice([True, False]),
            is_archived=random.choice([True, False]),
            is_important=random.choice([True, False]),
        )

    return {
        'categories': categories
    }


@pytest.fixture
def bookkeeping_data(db, users):
    """Create bookkeeping models: 100 categories + 100 partners + 150 transactions."""
    from bookkeeping.models import Category, Partner, Transaction

    bk_categories = []
    for i in range(1, 101):
        name = 'BKCategory{}'.format(i)
        cat, _ = Category.objects.get_or_create(name=name)
        bk_categories.append(cat)

    partners = []
    for i in range(1, 101):
        name = 'Partner {}'.format(i)
        email = 'partner{}@example.com'.format(i)
        phone = '+48 {}'.format(random.randint(100000000, 999999999))
        p, _ = Partner.objects.get_or_create(name=name, defaults={
            'email': email,
            'phone': phone,
            'city': 'Warsaw'
        })
        partners.append(p)

    user = users[0]
    for i in range(1, 151):
        note = 'Transaction {}'.format(i)
        Transaction.objects.create(
            type=random.choice(['I', 'O']),
            category=random.choice(bk_categories),
            partner=random.choice(partners),
            amount=round(random.uniform(10, 10000), 8),
            note=note,
            author=user,
            created_date=timezone.now().date(),
            payment_received_date=timezone.now().date(),
        )

    return {
        'categories': bk_categories,
        'partners': partners
    }


@pytest.fixture
def chat_data(db, users):
    """Create chat models: 100 rooms + 200 messages + related models."""
    from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
    from chat.utils import send_message_to_room

    rooms = []
    for i in range(1, 101):
        title = 'ChatRoom{}'.format(i)
        room, _ = Room.objects.get_or_create(title=title, defaults={
            'public': random.choice([True, False]),
            'archived': random.choice([True, False]),
            'protected': random.choice([True, False]),
        })
        room.allowed.add(*random.sample(users, k=min(3, len(users))))
        rooms.append(room)

    # Create 200 messages using send_message_to_room where possible
    for i in range(1, 201):
        room = random.choice(rooms)
        sender = random.choice(users)
        text = 'Message {} via send_message_to_room'.format(i)
        try:
            send_message_to_room(
                room_title=room.title,
                message_text=text,
                sender=sender,
                anonymous=random.choice([True, False]),
            )
        except Exception:
            Message.objects.create(
                sender=sender,
                text=text,
                room=room,
                anonymous=random.choice([True, False]),
            )

    # Create 100 message histories
    messages = list(Message.objects.all()[:100])
    for msg in messages:
        MessageHistory.objects.get_or_create(message=msg)

    # Create 150 history entries
    histories = list(MessageHistory.objects.all())
    for i in range(1, 151):
        text = 'History entry {}'.format(i)
        MessageHistoryEntry.objects.create(
            history=random.choice(histories),
            text=text,
        )

    # Create 100 attachments
    messages = list(Message.objects.all())
    for i in range(1, 101):
        filename = 'file_{}.txt'.format(i)
        MessageAttachment.objects.create(
            type=random.choice(['image', 'document', 'video']),
            filename=filename,
            message=random.choice(messages),
        )

    # Create 200 read-by records
    for i in range(1, 201):
        MessageReadBy.objects.create(
            message=random.choice(messages),
            user=random.choice(users),
        )

    return {
        'rooms': rooms
    }


@pytest.fixture
def elibrary_data(db, users):
    """Create elibrary models: 100 books."""
    from elibrary.models import Book

    user = users[0]
    for i in range(1, 101):
        title = 'Book Title {}'.format(i)
        author = 'Author {}'.format(i % 10)
        abstract = 'Abstract for book {}'.format(i)
        Book.objects.create(
            title=title,
            author=author,
            abstract=abstract,
            uploader=user,
            uploaded=timezone.now(),
        )


@pytest.fixture
def events_data(db):
    """Create events models: 100 events."""
    from events.models import Event

    for i in range(1, 101):
        title = 'Event {}'.format(i)
        description = 'Description for event {}'.format(i)
        Event.objects.create(
            title=title,
            description=description,
            place='Online',
            start_date=timezone.now() + timedelta(days=i),
            frequency='once',
            is_active=True,
        )


@pytest.fixture
def glosowania_data(db, users, chat_data):
    """Create glosowania models: 100 decyzje + related models."""
    from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

    rooms = chat_data.get('rooms', [])
    decyzje = []
    for i in range(1, 101):
        title = 'Bill {}: Test law'.format(i)
        d, _ = Decyzja.objects.get_or_create(title=title, defaults={
            'tresc': 'Law text {}'.format(i),
            'kara': 'Penalty {}'.format(i),
            'author': random.choice(users),
        })
        decyzje.append(d)

    # Create 200 arguments
    for i in range(1, 201):
        content = 'Argument {} content'.format(i)
        Argument.objects.create(
            decyzja=random.choice(decyzje),
            author=random.choice(users),
            argument_type=random.choice(['FOR', 'AGAINST']),
            content=content,
        )

    # Create 300 zebrane podpisy
    for i in range(1, 301):
        ZebranePodpisy.objects.create(
            projekt=random.choice(decyzje),
            podpis_uzytkownika=random.choice(users),
        )

    # Create 200 kto juz glosowal
    for i in range(1, 201):
        KtoJuzGlosowal.objects.create(
            projekt=random.choice(decyzje),
            ktory_uzytkownik_juz_zaglosowal=random.choice(users),
        )

    # Create 150 vote codes
    for i in range(1, 151):
        code = 'CODE{:04d}'.format(i)
        VoteCode.objects.create(
            project=random.choice(decyzje),
            code=code,
            vote=random.choice([True, False]),
        )

    return {
        'decyzje': decyzje
    }


@pytest.fixture
def home_data(db, users):
    """Create home models: 100 feed items + 100 read statuses + onboarding."""
    from home.models import FeedItem, OnboardingProgress, ReadStatus

    for i in range(1, 101):
        title = 'FeedItem {}'.format(i)
        description = 'Description {}'.format(i)
        FeedItem.objects.create(
            content_type=random.choice(['post', 'task', 'book']),
            object_id=i,
            title=title,
            description=description,
            author=random.choice(users),
            timestamp=timezone.now(),
            url='/item/{}'.format(i),
        )

    for i in range(1, 101):
        ReadStatus.objects.create(
            user=random.choice(users),
            content_type=random.choice(['post', 'task', 'book']),
            object_id=i,
        )

    for i in range(1, 101):
        user = random.choice(users)
        OnboardingProgress.objects.get_or_create(user=user, defaults={
            'step_argued': random.choice([True, False]),
            'step_chatted': random.choice([True, False]),
            'step_voted': random.choice([True, False]),
        })


@pytest.fixture
def obywatele_data(db):
    """Create obywatele models: 100 uzytkownicy + related models."""
    from obywatele.models import CitizenActivity, Rate, Uzytkownik

    citizens = []
    for i in range(1, 101):
        username = 'citizen{}'.format(i)
        email = 'citizen{}@example.com'.format(i)
        user, _ = User.objects.get_or_create(username=username, defaults={
            'email': email
        })
        phone = '+48 {}'.format(random.randint(100000000, 999999999))
        uz, _ = Uzytkownik.objects.get_or_create(uid=user, defaults={
            'reputation': random.randint(-10, 100),
            'city': 'Warsaw',
            'phone': phone,
        })
        citizens.append(uz)

    for i in range(1, 151):
        description = 'Activity {}'.format(i)
        CitizenActivity.objects.create(
            uzytkownik=random.choice(citizens),
            activity_type=random.choice(['new_candidate', 'user_activated', 'user_blocked']),
            description=description,
        )

    for i in range(1, 201):
        Rate.objects.create(
            kandydat=random.choice(citizens),
            obywatel=random.choice(citizens),
            rate=random.randint(-5, 5),
        )

    return {
        'citizens': citizens
    }


@pytest.fixture
def all_models(db, users, board_data, bookkeeping_data, chat_data, elibrary_data, events_data, glosowania_data, home_data, obywatele_data):
    """Create all models."""
    pass


def test_board_models_count(db, board_data):
    from board.models import Post, PostCategory
    assert PostCategory.objects.count() >= 100
    assert Post.objects.count() >= 100


def test_bookkeeping_models_count(db, bookkeeping_data):
    from bookkeeping.models import Category, Partner, Transaction
    assert Category.objects.count() >= 100
    assert Partner.objects.count() >= 100
    assert Transaction.objects.count() >= 150


def test_chat_models_count(db, chat_data):
    from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
    assert Room.objects.count() >= 100
    assert Message.objects.count() >= 200
    assert MessageHistory.objects.count() >= 100
    assert MessageHistoryEntry.objects.count() >= 150
    assert MessageAttachment.objects.count() >= 100
    assert MessageReadBy.objects.count() >= 200


def test_elibrary_models_count(db, elibrary_data):
    from elibrary.models import Book
    assert Book.objects.count() >= 100


def test_events_models_count(db, events_data):
    from events.models import Event
    assert Event.objects.count() >= 100


def test_glosowania_models_count(db, glosowania_data):
    from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
    assert Decyzja.objects.count() >= 100
    assert Argument.objects.count() >= 200
    assert ZebranePodpisy.objects.count() >= 300
    assert KtoJuzGlosowal.objects.count() >= 200
    assert VoteCode.objects.count() >= 150


def test_home_models_count(db, home_data):
    from home.models import FeedItem, OnboardingProgress, ReadStatus
    assert FeedItem.objects.count() >= 100
    assert ReadStatus.objects.count() >= 100
    # OnboardingProgress may have up to 20 unique users
    assert OnboardingProgress.objects.count() >= 20


def test_obywatele_models_count(db, obywatele_data):
    from obywatele.models import CitizenActivity, Rate, Uzytkownik
    assert Uzytkownik.objects.count() >= 100
    assert CitizenActivity.objects.count() >= 150
    assert Rate.objects.count() >= 200


def test_summary_all_models(db, all_models):
    """Summary test to verify all models have 100+ records."""
    from board.models import Post, PostCategory
    from bookkeeping.models import Category as BKCategory
    from bookkeeping.models import Partner, Transaction
    from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
    from elibrary.models import Book
    from events.models import Event
    from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
    from home.models import FeedItem, OnboardingProgress, ReadStatus
    from obywatele.models import CitizenActivity, Rate, Uzytkownik

    min_counts = {
        'PostCategory': (PostCategory, 100),
        'Post': (Post, 100),
        'BKCategory': (BKCategory, 100),
        'Partner': (Partner, 100),
        'Transaction': (Transaction, 150),
        'Room': (Room, 100),
        'Message': (Message, 200),
        'MessageHistory': (MessageHistory, 100),
        'MessageHistoryEntry': (MessageHistoryEntry, 150),
        'MessageAttachment': (MessageAttachment, 100),
        'MessageReadBy': (MessageReadBy, 200),
        'Book': (Book, 100),
        'Event': (Event, 100),
        'Decyzja': (Decyzja, 100),
        'Argument': (Argument, 200),
        'ZebranePodpisy': (ZebranePodpisy, 300),
        'KtoJuzGlosowal': (KtoJuzGlosowal, 200),
        'VoteCode': (VoteCode, 150),
        'FeedItem': (FeedItem, 100),
        'ReadStatus': (ReadStatus, 100),
        'OnboardingProgress': (OnboardingProgress, 20),
        'Uzytkownik': (Uzytkownik, 100),
        'CitizenActivity': (CitizenActivity, 150),
        'Rate': (Rate, 200),
    }

    print("\n=== SUMMARY: Model Record Counts ===")
    all_pass = True
    for model_name, (model_class, min_count) in min_counts.items():
        count = model_class.objects.count()
        status = "PASS" if count >= min_count else "FAIL"
        if count < min_count:
            all_pass = False
        print("{}: {} records (min: {}) - {}".format(model_name, count, min_count, status))

    assert all_pass, "Some models don't have enough records!"
