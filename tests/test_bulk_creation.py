"""
Unit tests that create 100+ records per model using actual application logic.
Run with: python manage.py test tests.test_bulk_creation --verbosity=2
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()


class BulkCreationTest(TestCase):
    """Test that creates 100+ records for each model using actual Django ORM."""
    def test_create_board_models(self):
        from board.models import Post, PostCategory

        # Create 100 categories
        categories = []
        for i in range(1, 101):
            cat, _ = PostCategory.objects.get_or_create(name='Category%d' % i, defaults={
                'priority': i % 10 + 1
            })
            categories.append(cat)

        # Create users
        users = []
        for i in range(1, 6):
            user, _ = User.objects.get_or_create(username='boarduser%d' % i, defaults={
                'email': 'board%d@example.com' % i
            })
            users.append(user)

        # Create 100 posts
        for i in range(1, 101):
            Post.objects.create(
                title='Article %d' % i,
                subtitle='Subtitle %d' % i,
                text='<p>Content of article %d</p>' % i,
                author=random.choice(users),
                category=random.choice(categories),
                is_public=random.choice([True, False]),
                is_archived=random.choice([True, False]),
                is_important=random.choice([True, False]),
            )

        self.assertEqual(PostCategory.objects.count(), 100)
        self.assertEqual(Post.objects.count(), 100)

    def test_create_bookkeeping_models(self):
        from bookkeeping.models import Category, Partner, Transaction

        # Create 100 categories
        bk_cats = []
        for i in range(1, 101):
            cat, _ = Category.objects.get_or_create(name='BKCategory%d' % i)
            bk_cats.append(cat)

        # Create 100 partners
        partners = []
        for i in range(1, 101):
            p, _ = Partner.objects.get_or_create(name='Partner%d' % i, defaults={
                'email': 'partner%d@example.com' % i,
                'phone': '+48 %d' % random.randint(100000000, 999999999),
                'city': 'Warsaw',
            })
            partners.append(p)

        # Create 150 transactions
        user, _ = User.objects.get_or_create(username='bkuser', defaults={
            'email': 'bk@example.com'
        })

        for i in range(1, 151):
            Transaction.objects.create(
                type=random.choice(['I', 'O']),
                category=random.choice(bk_cats),
                partner=random.choice(partners),
                amount=round(random.uniform(10, 10000), 8),
                note='Transaction %d' % i,
                author=user,
                created_date=timezone.now().date(),
                payment_received_date=timezone.now().date(),
            )

        self.assertEqual(Category.objects.count(), 100)
        self.assertEqual(Partner.objects.count(), 100)
        self.assertEqual(Transaction.objects.count(), 150)

    def test_create_chat_models(self):
        from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room

        # Create 100 rooms
        rooms = []
        users = []
        for i in range(1, 21):
            user, _ = User.objects.get_or_create(username='chatuser%d' % i, defaults={
                'email': 'chat%d@example.com' % i
            })
            users.append(user)

        for i in range(1, 101):
            room, _ = Room.objects.get_or_create(title='ChatRoom%d' % i, defaults={
                'public': random.choice([True, False]),
                'archived': random.choice([True, False]),
            })
            room.allowed.add(*random.sample(users, k=min(3, len(users))))
            rooms.append(room)

        # Create 200 messages
        for i in range(1, 201):
            Message.objects.create(
                sender=random.choice(users),
                text='Test message %d' % i,
                room=random.choice(rooms),
                anonymous=random.choice([True, False]),
            )

        # Create 100 message histories
        messages = Message.objects.all()[:100]
        for msg in messages:
            MessageHistory.objects.get_or_create(message=msg)

        # Create 150 history entries
        histories = MessageHistory.objects.all()
        for i in range(1, 151):
            MessageHistoryEntry.objects.create(
                history=random.choice(histories),
                text='History entry %d' % i,
            )

        # Create 100 attachments
        messages = Message.objects.all()
        for i in range(1, 101):
            MessageAttachment.objects.create(
                type=random.choice(['image', 'document']),
                filename='file_%d.txt' % i,
                message=random.choice(messages),
            )

        # Create 200 read-by records
        for i in range(1, 201):
            MessageReadBy.objects.create(
                message=random.choice(messages),
                user=random.choice(users),
            )

        self.assertEqual(Room.objects.count(), 100)
        self.assertEqual(Message.objects.count(), 200)
        self.assertEqual(MessageHistory.objects.count(), 100)
        self.assertEqual(MessageHistoryEntry.objects.count(), 150)
        self.assertEqual(MessageAttachment.objects.count(), 100)
        self.assertEqual(MessageReadBy.objects.count(), 200)

    def test_create_elibrary_models(self):
        from elibrary.models import Book

        user, _ = User.objects.get_or_create(username='libuser', defaults={
            'email': 'lib@example.com'
        })

        for i in range(1, 101):
            Book.objects.create(
                title='Book Title %d' % i,
                author='Author %d' % (i % 10),
                abstract='Abstract for book %d' % i,
                uploader=user,
                uploaded=timezone.now(),
            )

        self.assertEqual(Book.objects.count(), 100)

    def test_create_events_models(self):
        from events.models import Event

        for i in range(1, 101):
            Event.objects.create(
                title='Event %d' % i,
                description='Description for event %d' % i,
                place='Online',
                start_date=timezone.now() + timedelta(days=i),
                frequency='once',
                is_active=True,
            )

        self.assertEqual(Event.objects.count(), 100)

    def test_create_glosowania_models(self):
        from chat.models import Room
        from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

        # Create rooms for decyzja
        rooms = []
        for i in range(1, 6):
            room, _ = Room.objects.get_or_create(title='VotingRoom%d' % i)
            rooms.append(room)

        # Create users
        users = []
        for i in range(1, 11):
            user, _ = User.objects.get_or_create(username='glosuser%d' % i, defaults={
                'email': 'glos%d@example.com' % i
            })
            users.append(user)

        # Create 100 decyzje
        decyzje = []
        for i in range(1, 101):
            d, _ = Decyzja.objects.get_or_create(title='Bill %d: Test law' % i, defaults={
                'tresc': 'Law text %d' % i,
                'kara': 'Penalty %d' % i,
                'author': random.choice(users),
            })
            decyzje.append(d)

        # Create 200 arguments
        for i in range(1, 201):
            Argument.objects.create(
                decyzja=random.choice(decyzje),
                author=random.choice(users),
                argument_type=random.choice(['FOR', 'AGAINST']),
                content='Argument %d content' % i,
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
            VoteCode.objects.create(
                project=random.choice(decyzje),
                code='CODE%04d' % i,
                vote=random.choice([True, False]),
            )

        self.assertEqual(Decyzja.objects.count(), 100)
        self.assertEqual(Argument.objects.count(), 200)
        self.assertEqual(ZebranePodpisy.objects.count(), 300)
        self.assertEqual(KtoJuzGlosowal.objects.count(), 200)
        self.assertEqual(VoteCode.objects.count(), 150)

    def test_create_home_models(self):
        from home.models import FeedItem, OnboardingProgress, ReadStatus

        users = []
        for i in range(1, 21):
            user, _ = User.objects.get_or_create(username='homeuser%d' % i, defaults={
                'email': 'home%d@example.com' % i
            })
            users.append(user)

        # Create 100 feed items
        for i in range(1, 101):
            FeedItem.objects.create(
                content_type=random.choice(['post', 'task', 'book']),
                object_id=i,
                title='FeedItem %d' % i,
                description='Description %d' % i,
                author=random.choice(users),
                timestamp=timezone.now(),
                url='/item/%d' % i,
            )

        # Create 100 read statuses
        for i in range(1, 101):
            ReadStatus.objects.create(
                user=random.choice(users),
                content_type=random.choice(['post', 'task']),
                object_id=i,
            )

        # Create 100 onboarding progress records
        for i in range(1, 101):
            user = random.choice(users)
            OnboardingProgress.objects.get_or_create(user=user, defaults={
                'step_argued': random.choice([True, False]),
                'step_chatted': random.choice([True, False]),
                'step_voted': random.choice([True, False]),
            })

        self.assertEqual(FeedItem.objects.count(), 100)
        self.assertEqual(ReadStatus.objects.count(), 100)
        # OnboardingProgress will have at most 20 records (unique users)
        self.assertGreaterEqual(OnboardingProgress.objects.count(), 20)

    def test_create_obywatele_models(self):
        from obywatele.models import CitizenActivity, Rate, Uzytkownik

        # Create 100 citizens
        citizens = []
        for i in range(1, 101):
            user, _ = User.objects.get_or_create(username='citizen%d' % i, defaults={
                'email': 'citizen%d@example.com' % i
            })
            uz, _ = Uzytkownik.objects.get_or_create(uid=user, defaults={
                'reputation': random.randint(-10, 100),
                'city': 'Warsaw',
            })
            citizens.append(uz)

        # Create 150 citizen activities
        for i in range(1, 151):
            CitizenActivity.objects.create(
                uzytkownik=random.choice(citizens),
                activity_type=random.choice(['new_candidate', 'user_activated']),
                description='Activity %d' % i,
            )

        # Create 200 rates
        for i in range(1, 201):
            Rate.objects.create(
                kandydat=random.choice(citizens),
                obywatel=random.choice(citizens),
                rate=random.randint(-5, 5),
            )

        self.assertEqual(Uzytkownik.objects.count(), 100)
        self.assertEqual(CitizenActivity.objects.count(), 150)
        self.assertEqual(Rate.objects.count(), 200)

    def test_summary_all_models(self):
        """Verify all models have 100+ records."""
        from board.models import Post, PostCategory
        from bookkeeping.models import Category as BKCategory
        from bookkeeping.models import Partner, Transaction
        from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
        from elibrary.models import Book
        from events.models import Event
        from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
        from home.models import FeedItem, OnboardingProgress, ReadStatus
        from obywatele.models import CitizenActivity, Rate, Uzytkownik

        print("\n=== SUMMARY: Model Record Counts ===")

        models_to_check = [
            ('PostCategory', PostCategory, 100),
            ('Post', Post, 100),
            ('BKCategory', BKCategory, 100),
            ('Partner', Partner, 100),
            ('Transaction', Transaction, 150),
            ('Room', Room, 100),
            ('Message', Message, 200),
            ('MessageHistory', MessageHistory, 100),
            ('MessageHistoryEntry', MessageHistoryEntry, 150),
            ('MessageAttachment', MessageAttachment, 100),
            ('MessageReadBy', MessageReadBy, 200),
            ('Book', Book, 100),
            ('Event', Event, 100),
            ('Decyzja', Decyzja, 100),
            ('Argument', Argument, 200),
            ('ZebranePodpisy', ZebranePodpisy, 300),
            ('KtoJuzGlosowal', KtoJuzGlosowal, 200),
            ('VoteCode', VoteCode, 150),
            ('FeedItem', FeedItem, 100),
            ('ReadStatus', ReadStatus, 100),
            ('OnboardingProgress', OnboardingProgress, 20),
            ('Uzytkownik', Uzytkownik, 100),
            ('CitizenActivity', CitizenActivity, 150),
            ('Rate', Rate, 200),
        ]

        all_pass = True
        for name, model, min_count in models_to_check:
            count = model.objects.count()
            status = "PASS" if count >= min_count else "FAIL"
            if count < min_count:
                all_pass = False
            print("%s: %d records (min: %d) - %s" % (name, count, min_count, status))

        self.assertTrue(all_pass, "Some models don't have enough records!")
