"""
Single comprehensive test that creates 100+ records for every model using actual application logic,
then verifies all models have the minimum required records.

Run with: python manage.py test tests.test_bulk_model_creation --verbosity=2
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from board.models import Post, PostCategory
from bookkeeping.models import Category as BKCategory
from bookkeeping.models import Partner, Transaction
from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
from elibrary.models import Book
from events.models import Event
from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
from home.models import FeedItem, OnboardingProgress, ReadStatus
from obywatele.models import CitizenActivity, Rate, Uzytkownik

User = get_user_model()


class BulkModelCreationTest(TestCase):
    """
    Test that creates 100+ records for every model using actual Django ORM logic.
    """
    @classmethod
    def setUpTestData(cls):
        """Create all test data once for the test class"""
        cls.create_all_models()

    @classmethod
    def create_all_models(cls):
        """Create 100+ records for each model using actual Django ORM logic"""

        # =====================
        # Create base users (20 users)
        # =====================
        cls.users = []
        for i in range(1, 21):
            user, _ = User.objects.get_or_create(username=f'testuser{i}', defaults={
                'email': f'test{i}@example.com'
            })
            cls.users.append(user)

        # =====================
        # BOARD MODELS
        # =====================

        # Create 100 categories
        cls.categories = []
        for i in range(1, 101):
            cat, _ = PostCategory.objects.get_or_create(name=f'Category {i}', defaults={
                'priority': i % 10 + 1
            })
            cls.categories.append(cat)

        # Create 100 posts
        for i in range(1, 101):
            Post.objects.create(
                title=f'Article {i}',
                subtitle=f'Subtitle {i}',
                text=f'<p>Content of article {i}</p>',
                author=random.choice(cls.users),
                category=random.choice(cls.categories),
                is_public=random.choice([True, False]),
                is_archived=random.choice([True, False]),
                is_important=random.choice([True, False]),
            )

        # =====================
        # BOOKKEEPING MODELS
        # =====================

        # Create 100 categories
        cls.bk_categories = []
        for i in range(1, 101):
            cat, _ = BKCategory.objects.get_or_create(name=f'BK Category {i}')
            cls.bk_categories.append(cat)

        # Create 100 partners
        cls.partners = []
        for i in range(1, 101):
            p, _ = Partner.objects.get_or_create(name=f'Partner {i}', defaults={
                'email': f'partner{i}@example.com',
                'phone': f'+48 {random.randint(100000000, 999999999)}',
                'city': 'Warsaw',
                'country': 'Poland',
            })
            cls.partners.append(p)

        # Create 150 transactions
        for i in range(1, 151):
            Transaction.objects.create(
                type=random.choice(['I', 'O']),
                category=random.choice(cls.bk_categories),
                partner=random.choice(cls.partners),
                amount=round(random.uniform(10, 10000), 8),
                note=f'Transaction {i}',
                author=random.choice(cls.users),
                created_date=timezone.now().date(),
                payment_received_date=timezone.now().date(),
            )

        # =====================
        # CHAT MODELS
        # =====================

        # Create 100 rooms
        cls.rooms = []
        for i in range(1, 101):
            room, _ = Room.objects.get_or_create(title=f'ChatRoom {i}', defaults={
                'public': random.choice([True, False]),
                'archived': random.choice([True, False]),
                'protected': random.choice([True, False]),
            })
            # Add allowed users
            sample_size = min(3, len(cls.users))
            room.allowed.add(*random.sample(cls.users, k=sample_size))
            cls.rooms.append(room)

        # Create 200 messages
        for i in range(1, 201):
            Message.objects.create(
                sender=random.choice(cls.users),
                text=f'Test message {i}',
                room=random.choice(cls.rooms),
                anonymous=random.choice([True, False]),
            )

        # Create 100 message histories
        messages = list(Message.objects.all()[:100])
        for msg in messages:
            MessageHistory.objects.get_or_create(message=msg)

        # Create 150 history entries
        histories = list(MessageHistory.objects.all())
        for i in range(1, 151):
            MessageHistoryEntry.objects.create(
                history=random.choice(histories),
                text=f'History entry {i}',
            )

        # Create 100 attachments
        messages = list(Message.objects.all())
        for i in range(1, 101):
            MessageAttachment.objects.create(
                type=random.choice(['image', 'document', 'video']),
                filename=f'file_{i}.txt',
                message=random.choice(messages),
            )

        # Create 200 read-by records
        for i in range(1, 201):
            MessageReadBy.objects.create(
                message=random.choice(messages),
                user=random.choice(cls.users),
            )

        # =====================
        # ELIBRARY MODELS
        # =====================

        for i in range(1, 101):
            Book.objects.create(
                title=f'Book Title {i}',
                author=f'Author {i % 10}',
                abstract=f'Abstract for book {i}',
                uploader=random.choice(cls.users),
                uploaded=timezone.now(),
            )

        # =====================
        # EVENTS MODELS
        # =====================

        for i in range(1, 101):
            Event.objects.create(
                title=f'Event {i}',
                description=f'Description for event {i}',
                place='Online',
                start_date=timezone.now() + timedelta(days=i),
                frequency=random.choice(['once', 'daily', 'weekly', 'monthly']),
                is_active=True,
                is_public=True,
            )

        # =====================
        # GLOSOWANIA MODELS
        # =====================

        # Create 100 decyzje (bills)
        cls.decyzje = []
        for i in range(1, 101):
            d, _ = Decyzja.objects.get_or_create(title=f'Bill {i}: Test law', defaults={
                'tresc': f'Law text {i}',
                'kara': f'Penalty {i}',
                'uzasadnienie': f'Reasoning {i}',
                'args_for': f'For {i}',
                'args_against': f'Against {i}',
                'ile_osob_podpisalo': random.randint(0, 50),
                'za': random.randint(0, 100),
                'przeciw': random.randint(0, 100),
                'status': random.randint(1, 5),
                'chat_room': random.choice(cls.rooms) if cls.rooms else None,
                'author': random.choice(cls.users),
            })
            cls.decyzje.append(d)

        # Create 200 arguments
        for i in range(1, 201):
            Argument.objects.create(
                decyzja=random.choice(cls.decyzje),
                author=random.choice(cls.users),
                argument_type=random.choice(['FOR', 'AGAINST']),
                content=f'Argument {i} content',
            )

        # Create 300 zebrane podpisy (signatures)
        for i in range(1, 301):
            ZebranePodpisy.objects.create(
                projekt=random.choice(cls.decyzje),
                podpis_uzytkownika=random.choice(cls.users),
            )

        # Create 200 kto juz glosowal (who already voted)
        for i in range(1, 201):
            KtoJuzGlosowal.objects.create(
                projekt=random.choice(cls.decyzje),
                ktory_uzytkownik_juz_zaglosowal=random.choice(cls.users),
            )

        # Create 150 vote codes
        for i in range(1, 151):
            VoteCode.objects.create(
                project=random.choice(cls.decyzje),
                code=f'CODE{i:04d}',
                vote=random.choice([True, False]),
            )

        # =====================
        # HOME MODELS
        # =====================

        # Create 100 feed items
        for i in range(1, 101):
            FeedItem.objects.create(
                content_type=random.choice(['post', 'task', 'book', 'event']),
                object_id=i,
                title=f'FeedItem {i}',
                description=f'Description {i}',
                author=random.choice(cls.users),
                timestamp=timezone.now(),
                url=f'/item/{i}',
            )

        # Create 100 read statuses
        for i in range(1, 101):
            ReadStatus.objects.create(
                user=random.choice(cls.users),
                content_type=random.choice(['post', 'task', 'book']),
                object_id=i,
            )

        # Create 100 onboarding progress records (for 20 unique users)
        for i in range(1, 101):
            user = random.choice(cls.users)
            OnboardingProgress.objects.get_or_create(user=user, defaults={
                'step_argued': random.choice([True, False]),
                'step_chatted': random.choice([True, False]),
                'step_voted': random.choice([True, False]),
            })

        # =====================
        # OBYWATELE MODELS
        # =====================

        # Create 100 uzytkownicy (citizens)
        cls.citizens = []
        for i in range(1, 101):
            user, _ = User.objects.get_or_create(username=f'citizen_{i}', defaults={
                'email': f'citizen{i}@example.com'
            })
            uz, _ = Uzytkownik.objects.get_or_create(uid=user, defaults={
                'reputation': random.randint(-10, 100),
                'city': 'Warsaw',
                'phone': f'+48 {random.randint(100000000, 999999999)}',
            })
            cls.citizens.append(uz)

        # Create 150 citizen activities
        for i in range(1, 151):
            CitizenActivity.objects.create(
                uzytkownik=random.choice(cls.citizens),
                activity_type=random.choice(['new_candidate', 'user_activated', 'user_blocked']),
                description=f'Activity {i}',
            )

        # Create 200 rates
        for i in range(1, 201):
            Rate.objects.create(
                kandydat=random.choice(cls.citizens),
                obywatel=random.choice(cls.citizens),
                rate=random.randint(-5, 5),
            )

    def test_all_models_have_100_plus_records(self):
        """Verify all models have the minimum required records"""

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
            'OnboardingProgress': (OnboardingProgress, 20),  # Only 20 unique users
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
            print(f"{model_name}: {count} records (min: {min_count}) - {status}")

        self.assertTrue(all_pass, "Some models don't have enough records!")
