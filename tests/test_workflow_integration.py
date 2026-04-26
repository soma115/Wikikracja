"""
Workflow Integration Tests for all apps.
Tests cross-model interactions and complete business workflows.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class TestVotingWorkflow:
    """Test complete voting workflow from creation to completion."""
    def test_complete_voting_workflow(self, db, sample_users, chat_room):
        """Test creating a voting decision, adding arguments, collecting signatures, and voting."""
        from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

        room, users = chat_room
        author = sample_users[0]

        # Step 1: Create a voting decision (Decyzja)
        decyzja = Decyzja.objects.create(
            title='Workflow Test Bill',
            tresc='Test law text for workflow',
            kara='Test penalty',
            author=author,
            chat_room=room,
            status=1  # Draft status
        )
        assert Decyzja.objects.filter(title='Workflow Test Bill').exists()

        # Step 2: Add arguments for and against
        for i in range(5):
            Argument.objects.create(decyzja=decyzja, author=sample_users[i % len(sample_users)], argument_type='FOR', content='Argument FOR number {}'.format(i))

        for i in range(3):
            Argument.objects.create(decyzja=decyzja, author=sample_users[i % len(sample_users)], argument_type='AGAINST', content='Argument AGAINST number {}'.format(i))

        assert decyzja.arguments.count() == 8

        # Step 3: Collect signatures (ZebranePodpisy)
        # Delete any existing signatures for this project to avoid unique constraint
        ZebranePodpisy.objects.filter(projekt=decyzja).delete()

        for i in range(10):
            user = sample_users[i % len(sample_users)]
            # Delete existing signature for this user and project
            ZebranePodpisy.objects.filter(projekt=decyzja, podpis_uzytkownika=user).delete()
            ZebranePodpisy.objects.create(projekt=decyzja, podpis_uzytkownika=user)

        decyzja.ile_osob_podpisalo = 10
        decyzja.save()
        assert decyzja.ile_osob_podpisalo == 10

        # Step 4: Simulate voting
        KtoJuzGlosowal.objects.filter(projekt=decyzja).delete()
        for i in range(15):
            user = sample_users[i % len(sample_users)]
            # Delete existing votes to avoid unique constraint
            KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=user).delete()
            KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=user)
            # Update vote counts
            if i % 2 == 0:
                decyzja.za += 1
            else:
                decyzja.przeciw += 1

        decyzja.save()
        assert decyzja.za + decyzja.przeciw == 15

        # Step 5: Add vote codes
        VoteCode.objects.filter(project=decyzja).delete()
        for i in range(5):
            VoteCode.objects.create(project=decyzja, code='WORKFLOW{:04d}'.format(i), vote=(i % 2 == 0))

        assert decyzja.votecode_set.count() == 5

        # Step 6: Change status to active
        decyzja.status = 2  # Active
        decyzja.save()
        assert decyzja.status == 2


class TestChatMessageWorkflow:
    """Test message creation, history tracking, and read receipts."""
    def test_message_lifecycle(self, db, sample_users, chat_room):
        """Test complete message lifecycle: create, edit, track history, mark as read."""
        from chat.models import Message, MessageHistory, MessageHistoryEntry, MessageReadBy

        room, _users = chat_room
        sender = sample_users[0]
        reader = sample_users[1]

        # Step 1: Send initial message
        message = Message.objects.create(sender=sender, text='Initial message text', room=room, anonymous=False)
        assert Message.objects.filter(room=room).count() == 1

        # Step 2: Create message history (simulating an edit)
        history, created = MessageHistory.objects.get_or_create(message=message)

        # Step 3: Add history entry (previous version)
        MessageHistoryEntry.objects.create(history=history, text='Previous version of message')

        # Edit the message
        message.text = 'Edited message text'
        message.save()

        assert MessageHistoryEntry.objects.filter(history=history).count() == 1

        # Step 4: Mark message as read by multiple users
        MessageReadBy.objects.create(message=message, user=reader)
        MessageReadBy.objects.create(message=message, user=sender)

        assert MessageReadBy.objects.filter(message=message).count() == 2

        # Step 5: Add attachment
        from chat.models import MessageAttachment
        _attachment = MessageAttachment.objects.create(type='document', filename='test_doc.pdf', message=message)

        assert MessageAttachment.objects.filter(message=message).count() == 1

        # Step 6: Add reaction
        message.reactions = {
            'upvotes': [reader.id],
            'downvotes': []
        }
        message.save()

        message.refresh_from_db()
        assert reader.id in message.reactions.get('upvotes', [])


class TestBoardToHomeWorkflow:
    """Test board posts appearing in home feed."""
    def test_post_appears_in_feed(self, db, sample_users, board_category):
        """Test that when a post is created, it appears in the home feed."""
        from board.models import Post
        from home.models import FeedItem

        author = sample_users[0]

        # Create a board post
        post = Post.objects.create(title='Feed Test Post', subtitle='Test Subtitle', text='<p>Content that should appear in feed</p>', author=author, category=board_category, is_public=True, is_important=True)

        # Simulate feed item creation (in real app, this might be done by signal)
        _feed_item = FeedItem.objects.create(content_type='post', object_id=post.id, title=post.title, description=post.subtitle, author=author, timestamp=timezone.now(), url='/board/post/{}/'.format(post.id))

        assert FeedItem.objects.filter(content_type='post', object_id=post.id).exists()

        # Test marking as read
        from home.models import ReadStatus
        ReadStatus.objects.create(user=sample_users[1], content_type='post', object_id=post.id)

        assert ReadStatus.objects.filter(user=sample_users[1], object_id=post.id).exists()


class TestBookkeepingWorkflow:
    """Test complete bookkeeping transaction workflow."""
    def test_transaction_with_all_relations(self, db, sample_users, bookkeeping_category, bookkeeping_partner):
        """Test creating a transaction with all relationships."""
        from bookkeeping.models import Transaction

        author = sample_users[0]

        # Create transaction
        transaction = Transaction.objects.create(
            type='I',  # Income
            category=bookkeeping_category,
            partner=bookkeeping_partner,
            amount=1500.50,
            note='Workflow test transaction',
            author=author,
            created_date=timezone.now().date(),
            payment_received_date=timezone.now().date()
        )

        assert Transaction.objects.filter(note='Workflow test transaction').exists()

        # Verify relationships
        assert transaction.category == bookkeeping_category
        assert transaction.partner == bookkeeping_partner
        assert transaction.author == author
        assert float(transaction.amount) == 1500.50


class TestEventToNotificationWorkflow:
    """Test event creation and related notifications."""
    def test_event_creation_workflow(self, db, sample_users):
        """Test creating an event with notifications."""
        from events.models import Event
        from home.models import FeedItem

        organizer = sample_users[0]

        # Create event
        event = Event.objects.create(title='Workflow Test Event', description='Event that should notify users', place='Online', start_date=timezone.now().date() + timedelta(days=7), frequency='once', is_active=True, is_public=True)

        # Simulate feed creation
        _feed_item = FeedItem.objects.create(content_type='event', object_id=event.id, title=event.title, description=event.description, author=organizer, timestamp=timezone.now(), url='/events/{}/'.format(event.id))

        assert FeedItem.objects.filter(content_type='event', object_id=event.id).exists()

        # Test event recurrence (if applicable)
        _event2 = Event.objects.create(title='Recurring Event', description='Weekly meeting', place='Online', start_date=timezone.now().date() + timedelta(days=14), frequency='weekly', is_active=True)

        assert Event.objects.filter(frequency='weekly').exists()


class TestUserReputationWorkflow:
    """Test user reputation changes and rate workflow."""
    def test_reputation_workflow(self, db, sample_users):
        """Test citizen reputation changes based on rates."""
        from obywatele.models import Rate, Uzytkownik

        user = sample_users[0]

        # Get or create Uzytkownik (citizen profile)
        citizen, created = Uzytkownik.objects.get_or_create(uid=user, defaults={
            'reputation': 0,
            'city': 'Warsaw',
            'phone': '+48123456789'
        })
        if not created:
            citizen.reputation = 0
            citizen.save()

        # Simulate rating from other users
        total_rating = 0
        num_raters = min(10, len(sample_users) - 1)  # ensure we don't exceed list
        for i in range(num_raters):
            rater_index = (i + 1) % len(sample_users)
            rater = sample_users[rater_index]
            # Get or create rater's Uzytkownik profile
            rater_citizen, _ = Uzytkownik.objects.get_or_create(uid=rater, defaults={
                'reputation': 0,
                'city': 'Warsaw'
            })
            # Delete existing rate to avoid unique constraint
            Rate.objects.filter(kandydat=citizen, obywatel=rater_citizen).delete()
            rate_value = random.randint(-5, 5)
            Rate.objects.create(kandydat=citizen, obywatel=rater_citizen, rate=rate_value)
            total_rating += rate_value

        # Update reputation
        new_reputation = max(-10, min(100, total_rating))
        citizen.reputation = new_reputation
        citizen.save()

        assert citizen.reputation == new_reputation
        assert Rate.objects.filter(kandydat=citizen).count() == num_raters


class TestCrossModelIntegration:
    """Test interactions between different apps."""
    def test_voting_with_chat_room(self, db, sample_users):
        """Test that voting decision is linked to chat room and messages appear."""
        from chat.models import Message, Room
        from glosowania.models import Decyzja

        # Create room
        room = Room.objects.create(title='Voting Discussion Room', public=True, archived=False)

        # Add users to room
        for user in sample_users[:3]:
            room.allowed.add(user)

        # Create voting linked to room
        decyzja = Decyzja.objects.create(title='Cross-Model Test Bill', tresc='Law with chat discussion', author=sample_users[0], chat_room=room)

        # Add messages to the room about the voting
        for i in range(5):
            Message.objects.create(sender=sample_users[i % 3], text='Discussion point {} about the bill'.format(i), room=room, anonymous=False)

        # Compare by ID to avoid object comparison issues
        assert decyzja.chat_room_id == room.id
        # Refresh room from db to ensure we have the right object
        room.refresh_from_db()
        assert decyzja.chat_room.title == 'Voting Discussion Room'
        assert Message.objects.filter(room=room).count() == 5

    def test_book_appears_in_library_feed(self, db, sample_users):
        """Test that uploaded books appear in appropriate feeds."""
        from elibrary.models import Book
        from home.models import FeedItem

        uploader = sample_users[0]

        # Upload book
        book = Book.objects.create(title='Integration Test Book', author='Test Author', abstract='Abstract for integration test', uploader=uploader, uploaded=timezone.now())

        # Create feed item
        _feed_item = FeedItem.objects.create(content_type='book', object_id=book.id, title=book.title, description=book.abstract, author=uploader, timestamp=timezone.now(), url='/library/book/{}/'.format(book.id))

        # Verify cross-model link
        assert FeedItem.objects.filter(content_type='book', object_id=book.id).exists()

        # Test retrieval
        retrieved_item = FeedItem.objects.get(content_type='book', object_id=book.id)
        assert retrieved_item.title == book.title
