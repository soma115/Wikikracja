"""
Pytest tests that create 100+ records per model using actual Django ORM logic.
Uses send_message_to_room for chat messages where possible.

Run with: pytest tests/test_all_models_pytest.py -v
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
    users_list = []
    for i in range(1, 21):
        username = 'user{}'.format(i)
        email = 'user{}@example.com'.format(i)
        user, _ = User.objects.get_or_create(username=username, defaults={
            'email': email
        })
        users_list.append(user)
    return users_list


def test_create_board_models(db, users):
    """Create 100+ board models."""
    from board.models import Post, PostCategory

    # Create 100 categories
    categories = []
    for i in range(1, 101):
        name = 'Category{}'.format(i)
        cat, _ = PostCategory.objects.get_or_create(name=name, defaults={
            'priority': i % 10 + 1
        })
        categories.append(cat)

    # Create 100 posts
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

    assert PostCategory.objects.count() >= 100
    assert Post.objects.count() >= 100


def test_create_bookkeeping_models(db, users):
    """Create 100+ bookkeeping models."""
    from bookkeeping.models import Category, Partner, Transaction

    # Create 100 categories
    bk_cats = []
    for i in range(1, 101):
        name = 'BKCategory{}'.format(i)
        cat, _ = Category.objects.get_or_create(name=name)
        bk_cats.append(cat)

    # Create 100 partners
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

    # Create 150 transactions
    user = users[0]
    for i in range(1, 151):
        note = 'Transaction {}'.format(i)
        Transaction.objects.create(
            type=random.choice(['I', 'O']),
            category=random.choice(bk_cats),
            partner=random.choice(partners),
            amount=round(random.uniform(10, 10000), 8),
            note=note,
            author=user,
            created_date=timezone.now().date(),
            payment_received_date=timezone.now().date(),
        )

    assert Category.objects.count() >= 100
    assert Partner.objects.count() >= 100
    assert Transaction.objects.count() >= 150


def test_create_chat_models(db, users):
    """Create 100+ chat models using send_message_to_room where possible."""
    from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
    from chat.utils import send_message_to_room

    # Create 100 rooms
    rooms = []
    for i in range(1, 101):
        title = 'ChatRoom{}'.format(i)
        room, _ = Room.objects.get_or_create(title=title, defaults={
            'public': random.choice([True, False]),
            'archived': random.choice([True, False]),
            'protected': random.choice([True, False]),
        })
        # Add allowed users
        sample_size = min(3, len(users))
        room.allowed.add(*random.sample(users, k=sample_size))
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
            # Fallback to direct creation if send_message_to_room fails
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

    assert Room.objects.count() >= 100
    assert Message.objects.count() >= 200
    assert MessageHistory.objects.count() >= 100
    assert MessageHistoryEntry.objects.count() >= 150
    assert MessageAttachment.objects.count() >= 100
    assert MessageReadBy.objects.count() >= 200


def test_create_elibrary_models(db, users):
    """Create 100+ elibrary models."""
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

    assert Book.objects.count() >= 100


def test_create_events_models(db):
    """Create 100+ events models."""
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

    assert Event.objects.count() >= 100


def test_create_glosowania_models(db, users):
    """Create 100+ glosowania models."""
    from chat.models import Room
    from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

    # Create rooms for decyzja
    rooms = []
    for i in range(1, 6):
        room, _ = Room.objects.get_or_create(title='VotingRoom{}'.format(i))
        rooms.append(room)

    # Create 100 decyzje
    decyzje = []
    for i in range(1, 101):
        title = 'Bill {}: Test law'.format(i)
        d, _ = Decyzja.objects.get_or_create(title=title, defaults={
            'tresc': 'Law text {}'.format(i),
            'kara': 'Penalty {}'.format(i),
            'uzasadnienie': 'Reasoning {}'.format(i),
            'args_for': 'For {}'.format(i),
            'args_against': 'Against {}'.format(i),
            'ile_osob_podpisalo': random.randint(0, 50),
            'za': random.randint(0, 100),
            'przeciw': random.randint(0, 100),
            'status': random.randint(1, 5),
            'chat_room': random.choice(rooms) if rooms else None,
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

    assert Decyzja.objects.count() >= 100
    assert Argument.objects.count() >= 200
    assert ZebranePodpisy.objects.count() >= 300
    assert KtoJuzGlosowal.objects.count() >= 200
    assert VoteCode.objects.count() >= 150


def test_create_home_models(db, users):
    """Create 100+ home models."""
    from home.models import FeedItem, OnboardingProgress, ReadStatus

    # Create 100 feed items
    for i in range(1, 101):
        title = 'FeedItem {}'.format(i)
        description = 'Description {}'.format(i)
        FeedItem.objects.create(
            content_type=random.choice(['post', 'task', 'book', 'event']),
            object_id=i,
            title=title,
            description=description,
            author=random.choice(users),
            timestamp=timezone.now(),
            url='/item/{}'.format(i),
        )

    # Create 100 read statuses
    for i in range(1, 101):
        ReadStatus.objects.create(
            user=random.choice(users),
            content_type=random.choice(['post', 'task', 'book']),
            object_id=i,
        )

    # Create onboarding progress records (for 20 unique users)
    for i in range(1, 101):
        user = random.choice(users)
        OnboardingProgress.objects.get_or_create(user=user, defaults={
            'step_argued': random.choice([True, False]),
            'step_chatted': random.choice([True, False]),
            'step_voted': random.choice([True, False]),
        })

    assert FeedItem.objects.count() >= 100
    assert ReadStatus.objects.count() >= 100
    assert OnboardingProgress.objects.count() >= 20


def test_create_obywatele_models(db):
    """Create 100+ obywatele models."""
    from obywatele.models import CitizenActivity, Rate, Uzytkownik

    # Create 100 uzytkownicy
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

    # Create 150 citizen activities
    for i in range(1, 151):
        description = 'Activity {}'.format(i)
        CitizenActivity.objects.create(
            uzytkownik=random.choice(citizens),
            activity_type=random.choice(['new_candidate', 'user_activated', 'user_blocked']),
            description=description,
        )

    # Create 200 rates
    for i in range(1, 201):
        Rate.objects.create(
            kandydat=random.choice(citizens),
            obywatel=random.choice(citizens),
            rate=random.randint(-5, 5),
        )

    assert Uzytkownik.objects.count() >= 100
    assert CitizenActivity.objects.count() >= 150
    assert Rate.objects.count() >= 200


def test_summary_all_models(db, users):
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
