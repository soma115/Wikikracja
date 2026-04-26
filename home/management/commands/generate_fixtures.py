"""
Management command to generate fixtures with 100+ records for all models.
Run with: python manage.py generate_fixtures
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate fixtures with 100+ records for all models'

    def handle(self, *args, **options):
        self.stdout.write('Generating fixtures...')
        self.create_users()
        self.generate_board_fixtures()
        self.generate_bookkeeping_fixtures()
        self.generate_chat_fixtures()
        self.generate_elibrary_fixtures()
        self.generate_events_fixtures()
        self.generate_glosowania_fixtures()
        self.generate_home_fixtures()
        self.generate_obywatele_fixtures()
        self.stdout.write(self.style.SUCCESS('Successfully generated all fixtures!'))

    def create_users(self):
        """Create 20 test users."""
        for i in range(1, 21):
            username = 'user{}'.format(i)
            email = 'user{}@example.com'.format(i)
            User.objects.get_or_create(username=username, defaults={
                'email': email
            })

    def generate_board_fixtures(self):
        """Generate board model fixtures."""
        from board.models import Post, PostCategory

        # Create 100 categories
        for i in range(1, 101):
            PostCategory.objects.get_or_create(name='Category{}'.format(i), defaults={
                'priority': i % 10 + 1
            })
        categories = PostCategory.objects.all()
        data = serializers.serialize('json', categories)
        with open('board/fixtures/post_categories.json', 'w') as f:
            f.write(data)

        # Create 100 posts
        users = list(User.objects.all()[:20])
        categories = list(PostCategory.objects.all())
        for i in range(1, 101):
            Post.objects.create(
                title='Article {}'.format(i),
                subtitle='Subtitle {}'.format(i),
                text='<p>Content of article {}</p>'.format(i),
                author=random.choice(users),
                category=random.choice(categories),
                is_public=random.choice([True, False]),
                is_archived=random.choice([True, False]),
                is_important=random.choice([True, False]),
            )
        posts = Post.objects.all()
        data = serializers.serialize('json', posts)
        with open('board/fixtures/board.json', 'w') as f:
            f.write(data)

    def generate_bookkeeping_fixtures(self):
        """Generate bookkeeping model fixtures."""
        from bookkeeping.models import Category, Partner, Transaction

        # Create 100 categories
        for i in range(1, 101):
            Category.objects.get_or_create(name='BKCategory{}'.format(i))
        categories = Category.objects.all()
        data = serializers.serialize('json', categories)
        with open('bookkeeping/fixtures/categories.json', 'w') as f:
            f.write(data)

        # Create 100 partners
        for i in range(1, 101):
            Partner.objects.get_or_create(name='Partner {}'.format(i), defaults={
                'email': 'partner{}@example.com'.format(i),
                'phone': '+48 {}'.format(random.randint(100000000, 999999999)),
                'city': 'Warsaw',
                'country': 'Poland'
            })
        partners = Partner.objects.all()
        data = serializers.serialize('json', partners)
        with open('bookkeeping/fixtures/partners.json', 'w') as f:
            f.write(data)

        # Create 150 transactions
        users = list(User.objects.all()[:1])
        categories = list(Category.objects.all())
        partners = list(Partner.objects.all())
        for i in range(1, 151):
            Transaction.objects.create(
                type=random.choice(['I', 'O']),
                category=random.choice(categories),
                partner=random.choice(partners),
                amount=round(random.uniform(10, 10000), 8),
                note='Transaction {}'.format(i),
                author=random.choice(users),
                created_date=timezone.now().date(),
                payment_received_date=timezone.now().date(),
            )
        transactions = Transaction.objects.all()
        data = serializers.serialize('json', transactions)
        with open('bookkeeping/fixtures/transactions.json', 'w') as f:
            f.write(data)

    def generate_chat_fixtures(self):
        """Generate chat model fixtures."""
        from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room

        users = list(User.objects.all()[:20])
        # Create 100 rooms
        for i in range(1, 101):
            room, created = Room.objects.get_or_create(title='ChatRoom{}'.format(i), defaults={
                'public': random.choice([True, False]),
                'archived': random.choice([True, False]),
                'protected': random.choice([True, False]),
            })
            if created:
                sample_size = min(3, len(users))
                allowed_users = random.sample(users, sample_size)
                for user in allowed_users:
                    room.allowed.add(user)

        rooms = Room.objects.all()
        data = serializers.serialize('json', rooms)
        with open('chat/fixtures/chat_room.json', 'w') as f:
            f.write(data)

        # Create 200 messages
        rooms = list(Room.objects.all())
        for i in range(1, 201):
            Message.objects.create(
                sender=random.choice(users),
                text='Message {}'.format(i),
                room=random.choice(rooms),
                anonymous=random.choice([True, False]),
            )
        messages = Message.objects.all()
        data = serializers.serialize('json', messages)
        with open('chat/fixtures/messages.json', 'w') as f:
            f.write(data)

        # Create 100 message histories
        messages = list(Message.objects.all()[:100])
        for msg in messages:
            MessageHistory.objects.get_or_create(message=msg)
        histories = MessageHistory.objects.all()
        data = serializers.serialize('json', histories)
        with open('chat/fixtures/message_histories.json', 'w') as f:
            f.write(data)

        # Create 150 history entries
        histories = list(MessageHistory.objects.all())
        for i in range(1, 151):
            MessageHistoryEntry.objects.create(
                history=random.choice(histories),
                text='History entry {}'.format(i),
            )
        entries = MessageHistoryEntry.objects.all()
        data = serializers.serialize('json', entries)
        with open('chat/fixtures/message_history_entries.json', 'w') as f:
            f.write(data)

        # Create 100 attachments
        messages = list(Message.objects.all())
        for i in range(1, 101):
            MessageAttachment.objects.create(
                type=random.choice(['image', 'document', 'video']),
                filename='file_{}.txt'.format(i),
                message=random.choice(messages),
            )
        attachments = MessageAttachment.objects.all()
        data = serializers.serialize('json', attachments)
        with open('chat/fixtures/message_attachments.json', 'w') as f:
            f.write(data)

        # Create 200 read-by records
        messages = list(Message.objects.all())
        for i in range(1, 201):
            MessageReadBy.objects.create(
                message=random.choice(messages),
                user=random.choice(users),
            )
        readby = MessageReadBy.objects.all()
        data = serializers.serialize('json', readby)
        with open('chat/fixtures/message_read_by.json', 'w') as f:
            f.write(data)

    def generate_elibrary_fixtures(self):
        """Generate elibrary model fixtures."""
        from elibrary.models import Book

        users = list(User.objects.all()[:1])
        for i in range(1, 101):
            Book.objects.create(
                title='Book Title {}'.format(i),
                author='Author {}'.format(i % 10),
                abstract='Abstract for book {}'.format(i),
                uploader=random.choice(users),
                uploaded=timezone.now(),
            )
        books = Book.objects.all()
        data = serializers.serialize('json', books)
        with open('elibrary/fixtures/books.json', 'w') as f:
            f.write(data)

    def generate_events_fixtures(self):
        """Generate events model fixtures."""
        from events.models import Event

        for i in range(1, 101):
            Event.objects.create(
                title='Event {}'.format(i),
                description='Description for event {}'.format(i),
                place='Online',
                start_date=timezone.now() + timedelta(days=i),
                frequency='once',
                is_active=True,
            )
        events = Event.objects.all()
        data = serializers.serialize('json', events)
        with open('events/fixtures/events.json', 'w') as f:
            f.write(data)

    def generate_glosowania_fixtures(self):
        """Generate glosowania model fixtures."""
        from chat.models import Room
        from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

        users = list(User.objects.all()[:20])
        # Create rooms for decyzja
        for i in range(1, 6):
            Room.objects.get_or_create(title='VotingRoom{}'.format(i))

        # Create 100 decyzje
        for i in range(1, 101):
            Decyzja.objects.get_or_create(title='Bill {}: Test law'.format(i), defaults={
                'tresc': 'Law text {}'.format(i),
                'kara': 'Penalty {}'.format(i),
                'author': random.choice(users),
            })
        decyzje = Decyzja.objects.all()
        data = serializers.serialize('json', decyzje)
        with open('glosowania/fixtures/votings.json', 'w') as f:
            f.write(data)

        # Create 200 arguments
        decyzje = list(Decyzja.objects.all())
        for i in range(1, 201):
            Argument.objects.create(
                decyzja=random.choice(decyzje),
                author=random.choice(users),
                argument_type=random.choice(['FOR', 'AGAINST']),
                content='Argument {} content'.format(i),
            )
        arguments = Argument.objects.all()
        data = serializers.serialize('json', arguments)
        with open('glosowania/fixtures/arguments.json', 'w') as f:
            f.write(data)

        # Create 300 zebrane podpisy
        for i in range(1, 301):
            ZebranePodpisy.objects.create(
                projekt=random.choice(decyzje),
                podpis_uzytkownika=random.choice(users),
            )
        podpisy = ZebranePodpisy.objects.all()
        data = serializers.serialize('json', podpisy)
        with open('glosowania/fixtures/zebrane_podpisy.json', 'w') as f:
            f.write(data)

        # Create 200 kto juz glosowal
        for i in range(1, 201):
            KtoJuzGlosowal.objects.create(
                projekt=random.choice(decyzje),
                ktory_uzytkownik_juz_zaglosowal=random.choice(users),
            )
        kto = KtoJuzGlosowal.objects.all()
        data = serializers.serialize('json', kto)
        with open('glosowania/fixtures/kto_juz_glosowal.json', 'w') as f:
            f.write(data)

        # Create 150 vote codes
        for i in range(1, 151):
            VoteCode.objects.create(
                project=random.choice(decyzje),
                code='CODE{:04d}'.format(i),
                vote=random.choice([True, False]),
            )
        codes = VoteCode.objects.all()
        data = serializers.serialize('json', codes)
        with open('glosowania/fixtures/vote_codes.json', 'w') as f:
            f.write(data)

    def generate_home_fixtures(self):
        """Generate home model fixtures."""
        from home.models import FeedItem, OnboardingProgress, ReadStatus

        users = list(User.objects.all()[:20])
        # Create 100 feed items
        for i in range(1, 101):
            FeedItem.objects.create(
                content_type=random.choice(['post', 'task', 'book', 'event']),
                object_id=i,
                title='FeedItem {}'.format(i),
                description='Description {}'.format(i),
                author=random.choice(users),
                timestamp=timezone.now(),
                url='/item/{}'.format(i),
            )
        feed_items = FeedItem.objects.all()
        data = serializers.serialize('json', feed_items)
        with open('home/fixtures/feed_items.json', 'w') as f:
            f.write(data)

        # Create 100 read statuses
        for i in range(1, 101):
            ReadStatus.objects.create(
                user=random.choice(users),
                content_type=random.choice(['post', 'task', 'book']),
                object_id=i,
            )
        read_statuses = ReadStatus.objects.all()
        data = serializers.serialize('json', read_statuses)
        with open('home/fixtures/read_statuses.json', 'w') as f:
            f.write(data)

        # Create onboarding progress for 20 users
        for user in users:
            OnboardingProgress.objects.get_or_create(user=user, defaults={
                'step_argued': random.choice([True, False]),
                'step_chatted': random.choice([True, False]),
                'step_voted': random.choice([True, False]),
            })
        progress = OnboardingProgress.objects.all()
        data = serializers.serialize('json', progress)
        with open('home/fixtures/onboarding_progress.json', 'w') as f:
            f.write(data)

    def generate_obywatele_fixtures(self):
        """Generate obywatele model fixtures."""
        from obywatele.models import CitizenActivity, Rate, Uzytkownik

        # Create 100 citizens (Uzytkownik linked to User)
        for i in range(1, 101):
            username = 'citizen{}'.format(i)
            email = 'citizen{}@example.com'.format(i)
            user, _ = User.objects.get_or_create(username=username, defaults={
                'email': email
            })
            Uzytkownik.objects.get_or_create(uid=user, defaults={
                'reputation': random.randint(-10, 100),
                'city': 'Warsaw',
                'phone': '+48 {}'.format(random.randint(100000000, 999999999)),
            })

        citizens = Uzytkownik.objects.all()
        data = serializers.serialize('json', citizens)
        with open('obywatele/fixtures/uzytkownicy.json', 'w') as f:
            f.write(data)

        # Create 150 citizen activities
        citizens = list(Uzytkownik.objects.all())
        for i in range(1, 151):
            CitizenActivity.objects.create(
                uzytkownik=random.choice(citizens),
                activity_type=random.choice(['new_candidate', 'user_activated', 'user_blocked']),
                description='Activity {}'.format(i),
            )
        activities = CitizenActivity.objects.all()
        data = serializers.serialize('json', activities)
        with open('obywatele/fixtures/citizen_activities.json', 'w') as f:
            f.write(data)

        # Create 200 rates
        for i in range(1, 201):
            Rate.objects.create(
                kandydat=random.choice(citizens),
                obywatel=random.choice(citizens),
                rate=random.randint(-5, 5),
            )
        rates = Rate.objects.all()
        data = serializers.serialize('json', rates)
        with open('obywatele/fixtures/rates.json', 'w') as f:
            f.write(data)
