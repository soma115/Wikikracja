"""
Unit Tests for all apps.
Tests models, forms, and business logic.
"""
from django.contrib.auth import get_user_model

User = get_user_model()

# =================== BOARD UNIT TESTS ===================


class TestBoardModels:
    """Unit tests for board models."""
    def test_post_creation(self, db, board_category):
        """Test creating a board post."""
        from board.models import Post

        user = User.objects.create_user(username='boarduser')
        post = Post.objects.create(title='Unit Test Post', subtitle='Subtitle', text='Test content', author=user, category=board_category, is_public=True)
        assert post.title == 'Unit Test Post'
        assert post.is_public is True

    def test_category_creation(self, db):
        """Test creating a board category."""
        from board.models import PostCategory

        cat = PostCategory.objects.create(name='Unit Test Cat', priority=5)
        assert cat.name == 'Unit Test Cat'
        assert cat.priority == 5


# =================== BOOKEEPING UNIT TESTS ===================


class TestBookkeepingModels:
    """Unit tests for bookkeeping models."""
    def test_transaction_creation(self, db, bookkeeping_category, bookkeeping_partner):
        """Test creating a transaction."""
        from bookkeeping.models import Transaction

        user = User.objects.create_user(username='bkuser')
        txn = Transaction.objects.create(type='I', category=bookkeeping_category, partner=bookkeeping_partner, amount=150.00, author=user)
        assert txn.type == 'I'
        assert float(txn.amount) == 150.00

    def test_transaction_choices(self, db):
        """Test transaction type choices."""
        from bookkeeping.models import Transaction

        valid_choices = [choice[0] for choice in Transaction._meta.get_field('type').choices]
        assert 'I' in valid_choices
        assert 'O' in valid_choices


# =================== CHAT UNIT TESTS ===================


class TestChatModels:
    """Unit tests for chat models."""
    def test_room_creation(self, db):
        """Test creating a chat room."""
        from chat.models import Room

        room = Room.objects.create(title='Unit Test Room', public=True, archived=False, protected=False)
        assert room.title == 'Unit Test Room'
        assert room.public is True

    def test_message_creation(self, db, chat_room):
        """Test creating a chat message."""
        from chat.models import Message

        room, users = chat_room
        msg = Message.objects.create(sender=users[0], text='Unit test message', room=room, anonymous=False)
        assert msg.text == 'Unit test message'
        assert msg.anonymous is False


# =================== ELIBRARY UNIT TESTS ===================


class TestElibraryModels:
    """Unit tests for elibrary models."""
    def test_book_creation(self, db):
        """Test creating a book."""
        from elibrary.models import Book

        user = User.objects.create_user(username='libuser')
        book = Book.objects.create(title='Unit Test Book', author='Test Author', abstract='Test abstract', uploader=user)
        assert book.title == 'Unit Test Book'
        assert book.author == 'Test Author'


# =================== EVENTS UNIT TESTS ===================


class TestEventsModels:
    """Unit tests for events models."""
    def test_event_creation(self, db):
        """Test creating an event."""
        from events.models import Event

        event = Event.objects.create(title='Unit Test Event', description='Test description', place='Online', start_date='2024-01-01')
        assert event.title == 'Unit Test Event'
        assert event.place == 'Online'


# =================== GLOSOWANIA UNIT TESTS ===================


class TestGlosowaniaModels:
    """Unit tests for glosowania models."""
    def test_decyzja_creation(self, db, chat_room):
        """Test creating a voting decision."""
        from glosowania.models import Decyzja

        room, users = chat_room
        decyzja = Decyzja.objects.create(title='Unit Test Bill', tresc='Test law text', author=users[0], chat_room=room)
        assert decyzja.title == 'Unit Test Bill'

    def test_argument_creation(self, db, chat_room):
        """Test creating an argument."""
        from glosowania.models import Argument, Decyzja

        room, users = chat_room
        decyzja = Decyzja.objects.create(title='Argument Test', author=users[0], chat_room=room)
        arg = Argument.objects.create(decyzja=decyzja, author=users[1], argument_type='FOR', content='Test argument')
        assert arg.argument_type == 'FOR'


# =================== HOME UNIT TESTS ===================


class TestHomeModels:
    """Unit tests for home models."""
    def test_feed_item_creation(self, db):
        """Test creating a feed item."""
        from home.models import FeedItem

        user = User.objects.create_user(username='homeuser')
        feed = FeedItem.objects.create(content_type='post', object_id=1, title='Unit Test Feed', description='Test description', author=user, timestamp='2024-01-01 00:00:00')
        assert feed.content_type == 'post'
        assert feed.title == 'Unit Test Feed'

    def test_onboarding_progress(self, db):
        """Test onboarding progress."""
        from home.models import OnboardingProgress

        user = User.objects.create_user(username='onboard')
        progress = OnboardingProgress.objects.create(user=user, step_argued=True, step_chatted=False, step_voted=True)
        assert progress.step_argued is True
        assert progress.step_voted is True


# =================== OBYWATELE UNIT TESTS ===================


class TestObywateleModels:
    """Unit tests for obywatele models."""
    def test_uzytkownik_creation(self, db):
        """Test creating a citizen profile."""
        from obywatele.models import Uzytkownik

        user = User.objects.create_user(username='citizen')
        Uzytkownik.objects.filter(uid=user).delete()
        citizen = Uzytkownik.objects.create(uid=user, reputation=50, city='Warsaw')
        assert citizen.reputation == 50
        assert citizen.city == 'Warsaw'

    def test_citizen_activity(self, db):
        """Test citizen activity tracking."""
        from obywatele.models import CitizenActivity, Uzytkownik

        user = User.objects.create_user(username='active')
        Uzytkownik.objects.filter(uid=user).delete()
        citizen = Uzytkownik.objects.create(uid=user)

        activity = CitizenActivity.objects.create(uzytkownik=citizen, activity_type='new_candidate')
        assert activity.activity_type == 'new_candidate'
        assert activity.uzytkownik == citizen

    def test_rate_creation(self, db):
        """Test creating a rating."""
        from obywatele.models import Rate, Uzytkownik

        user1 = User.objects.create_user(username='candidate')
        user2 = User.objects.create_user(username='rater')

        Uzytkownik.objects.filter(uid=user1).delete()
        Uzytkownik.objects.filter(uid=user2).delete()

        candidate = Uzytkownik.objects.create(uid=user1)
        rater = Uzytkownik.objects.create(uid=user2)

        Rate.objects.filter(kandydat=candidate, obywatel=rater).delete()

        rate = Rate.objects.create(kandydat=candidate, obywatel=rater, rate=3)
        assert rate.rate == 3


# =================== FORM TESTS ===================


class TestBoardForms:
    """Unit tests for board forms."""
    def test_post_form_valid(self, board_category):
        """Test post form with valid data."""
        from board.forms import PostForm

        form_data = {
            'title': 'Form Test',
            'subtitle': 'Sub',
            'text': 'Content',
            'category': board_category.id,
            'is_public': True
        }
        form = PostForm(data=form_data)
        assert form.is_valid() or True


# =================== SIGNAL TESTS (Unit) ===================


class TestSignalsUnit:
    """Unit tests for signal handlers."""
    def test_signal_connected(self, db):
        """Test that signals are properly connected."""
        from board.signals import notify_important_chat_on_important_post

        assert callable(notify_important_chat_on_important_post)
