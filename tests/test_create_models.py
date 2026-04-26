"""
Unit-test style script that uses actual application logic to create 100+ records per model.
Designed to be run via:  python manage.py runscript test_create_models
or converted into proper Django TestCase files.
"""
import os
import random
from datetime import timedelta

# Setup Django environment
import django
from django.contrib.auth import get_user_model
from django.utils.timezone import now

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wikikracja.settings')
django.setup()

User = get_user_model()


# =====================
# Helper to ensure we have users
# =====================
def ensure_users(n=20):
    users = []
    for i in range(1, n + 1):
        user, _ = User.objects.get_or_create(username=f'testuser{i}', defaults=dict(
            email=f'test{i}@example.com',
            is_active=True,
        ))
        users.append(user)
    return users


# =====================
# BOARD
# =====================
def create_board_records(n=100):
    from board.models import Post, PostCategory

    users = ensure_users(5)
    categories = []
    for i in range(1, n + 1):
        cat, _ = PostCategory.objects.get_or_create(name=f'Category {i}', defaults=dict(priority=i % 10 + 1))
        categories.append(cat)

    for i in range(1, n + 1):
        Post.objects.create(
            title=f'Article {i}',
            subtitle=f'Subtitle {i}',
            text=f'<p>Content of article {i}</p>',
            author=random.choice(users),
            category=random.choice(categories),
            is_public=random.choice([True, False]),
            is_archived=random.choice([True, False]),
            is_important=random.choice([True, False]),
        )
    print(f'Board: created/ensured {n} posts and {n} categories')


# =====================
# BOOKKEEPING
# =====================
def create_bookkeeping_records(n=100):
    from bookkeeping.models import Category, Partner, Transaction

    users = ensure_users(3)
    categories = []
    for i in range(1, n + 1):
        cat, _ = Category.objects.get_or_create(name=f'BK Category {i}')
        categories.append(cat)

    partners = []
    for i in range(1, n + 1):
        p, _ = Partner.objects.get_or_create(name=f'Partner {i}', defaults=dict(
            email=f'partner{i}@example.com',
            phone=f'+48 {random.randint(100000000, 999999999)}',
            city='Warsaw',
            country='Poland',
        ))
        partners.append(p)

    for i in range(1, n + 1):
        Transaction.objects.create(
            type=random.choice(['I', 'O']),
            category=random.choice(categories),
            partner=random.choice(partners),
            amount=round(random.uniform(10, 10000), 8),
            note=f'Transaction {i}',
            author=random.choice(users),
            created_date=now().date(),
            payment_received_date=now().date(),
        )
    print(f'Bookkeeping: {n} transactions, {n} partners, {n} categories')


# =====================
# CHAT
# =====================
def create_chat_records(n=100):
    from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
    from chat.utils import send_message_to_room

    users = ensure_users(10)

    rooms = []
    for i in range(1, n + 1):
        room, _ = Room.objects.get_or_create(title=f'Chat Room {i}', defaults=dict(
            public=random.choice([True, False]),
            archived=random.choice([True, False]),
            protected=random.choice([True, False]),
            last_activity=now(),
        ))
        # Use actual logic: add allowed users via M2M
        room.allowed.add(*random.sample(users, k=3))
        rooms.append(room)

    # Use send_message_to_room for some messages
    for i in range(1, n + 1):
        room = random.choice(rooms)
        sender = random.choice(users)
        send_message_to_room(
            room_title=room.title,
            message_text=f'Message {i} via send_message_to_room',
            sender=sender,
            anonymous=random.choice([True, False]),
        )

    # Additional messages directly
    for i in range(n + 1, 2 * n + 1):
        Message.objects.create(
            sender=random.choice(users),
            text=f'Direct message {i}',
            room=random.choice(rooms),
            anonymous=random.choice([True, False]),
        )

    # Histories
    messages = Message.objects.order_by('?')[:n]
    for msg in messages:
        history, _ = MessageHistory.objects.get_or_create(message=msg)
        MessageHistoryEntry.objects.create(
            history=history,
            text=f'History entry for message {msg.pk}',
        )

    # Attachments
    for i in range(1, n + 1):
        MessageAttachment.objects.create(
            type=random.choice(['image', 'document', 'video']),
            filename=f'file_{i}.txt',
            message=random.choice(messages) if messages else Message.objects.first(),
        )

    # Read-by
    for i in range(1, n + 1):
        MessageReadBy.objects.create(
            message=random.choice(messages) if messages else Message.objects.first(),
            user=random.choice(users),
        )

    print(f'Chat: created {Message.objects.count()} messages, {n} rooms, attachments, histories')


# =====================
# ELIBRARY
# =====================
def create_elibrary_records(n=100):
    from elibrary.models import Book

    users = ensure_users(3)
    for i in range(1, n + 1):
        Book.objects.create(
            title=f'Book Title {i}',
            author=f'Author {i % 10}',
            abstract=f'Abstract for book {i}',
            uploader=random.choice(users),
            uploaded=now(),
        )
    print(f'Elibrary: {n} books')


# =====================
# EVENTS
# =====================
def create_events_records(n=100):
    from events.models import Event

    for i in range(1, n + 1):
        Event.objects.create(
            title=f'Event {i}',
            description=f'Description for event {i}',
            place='Online',
            start_date=now() + timedelta(days=i),
            frequency=random.choice(['once', 'daily', 'weekly', 'monthly']),
            is_active=True,
            is_public=True,
        )
    print(f'Events: {n} events')


# =====================
# GLOSOWANIA
# =====================
def create_glosowania_records(n=100):
    from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

    users = ensure_users(10)
    rooms = ensure_chat_rooms(5)

    decyzje = []
    for i in range(1, n + 1):
        d, _ = Decyzja.objects.get_or_create(title=f'Bill {i}: Sample law', defaults=dict(
            tresc=f'Law text {i}',
            kara=f'Penalty {i}',
            uzasadnienie=f'Reasoning {i}',
            args_for=f'For {i}',
            args_against=f'Against {i}',
            ile_osob_podpisalo=random.randint(0, 50),
            za=random.randint(0, 100),
            przeciw=random.randint(0, 100),
            status=random.randint(1, 5),
            chat_room=random.choice(rooms) if rooms else None,
            author=random.choice(users),
        ))
        decyzje.append(d)

    for i in range(1, 2 * n + 1):
        Argument.objects.create(
            decyzja=random.choice(decyzje),
            author=random.choice(users),
            argument_type=random.choice(['FOR', 'AGAINST']),
            content=f'Argument {i} content',
        )

    for i in range(1, 3 * n + 1):
        ZebranePodpisy.objects.create(
            projekt=random.choice(decyzje),
            podpis_uzytkownika=random.choice(users),
        )

    for i in range(1, 2 * n + 1):
        KtoJuzGlosowal.objects.create(
            projekt=random.choice(decyzje),
            ktory_uzytkownik_juz_zaglosowal=random.choice(users),
        )

    for i in range(1, n + 50 + 1):
        VoteCode.objects.create(
            project=random.choice(decyzje),
            code=f'CODE{i:04d}',
            vote=random.choice([True, False]),
        )

    print(f'Glosowania: {n} decyzje, arguments, podpisy, glosowania')


# =====================
# HOME
# =====================
def create_home_records(n=100):
    from home.models import FeedItem, OnboardingProgress, ReadStatus

    users = ensure_users(10)
    for i in range(1, n + 1):
        FeedItem.objects.create(
            content_type=random.choice(['post', 'task', 'book', 'event']),
            object_id=i,
            title=f'FeedItem {i}',
            description=f'Description {i}',
            author=random.choice(users),
            timestamp=now(),
            url=f'/item/{i}',
        )

    for i in range(1, n + 1):
        ReadStatus.objects.create(
            user=random.choice(users),
            content_type=random.choice(['post', 'task', 'book']),
            object_id=i,
        )

    for i in range(1, n + 1):
        ob, _ = OnboardingProgress.objects.get_or_create(user=User.objects.get_or_create(username=f'onboard_user_{i}', defaults=dict(email=f'onboard{i}@example.com'))[0], defaults=dict(
            step_argued=random.choice([True, False]),
            step_chatted=random.choice([True, False]),
            step_voted=random.choice([True, False]),
        ))
    print(f'Home: {n} feed items, read statuses, onboardingprogress')


# =====================
# OBYWATELE
# =====================
def create_obywatele_records(n=100):
    from obywatele.models import CitizenActivity, Rate, Uzytkownik

    _users = ensure_users(10)
    uzytkownicy = []
    for i in range(1, n + 1):
        user = User.objects.get_or_create(username=f'citizen_{i}', defaults=dict(email=f'citizen{i}@example.com'))[0]
        uz, _ = Uzytkownik.objects.get_or_create(uid=user, defaults=dict(
            reputation=random.randint(-10, 100),
            city='Warsaw',
            phone=f'+48 {random.randint(100000000, 999999999)}',
        ))
        uzytkownicy.append(uz)

    for i in range(1, 150 + 1):
        CitizenActivity.objects.create(
            uzytkownik=random.choice(uzytkownicy),
            activity_type=random.choice(['new_candidate', 'user_activated', 'user_blocked']),
            description=f'Activity {i}',
        )

    for i in range(1, 200 + 1):
        Rate.objects.create(
            kandydat=random.choice(uzytkownicy),
            obywatel=random.choice(uzytkownicy),
            rate=random.randint(-5, 5),
        )

    print(f'Obywatele: {n} uzytkownicy, activities, rates')


# =====================
# Helpers
# =====================
def ensure_chat_rooms(n=5):
    from chat.models import Room
    rooms = list(Room.objects.all()[:n])
    if not rooms:
        for i in range(1, n + 1):
            r, _ = Room.objects.get_or_create(title=f'Helper Room {i}', defaults=dict(public=True))
            rooms.append(r)
    return rooms


# =====================
# MAIN
# =====================
if __name__ == '__main__':
    print('Creating 100+ records per model using actual application logic...')
    create_board_records(100)
    create_bookkeeping_records(100)
    create_chat_records(100)
    create_elibrary_records(100)
    create_events_records(100)
    create_glosowania_records(100)
    create_home_records(100)
    create_obywatele_records(100)
    print('Done! All models have 100+ records created via logic.')
