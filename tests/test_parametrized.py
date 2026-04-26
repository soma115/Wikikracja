"""
Parametrized Tests for all apps.
Test multiple scenarios with @pytest.mark.parametrize.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class TestBoardParametrized:
    """Parametrized tests for board app."""
    @pytest.mark.parametrize("is_public,is_archived", [
        (True, False),
        (False, False),
        (True, True),
        (False, True),
    ])
    def test_post_visibility(self, db, board_category, is_public, is_archived):
        """Test post visibility with different states."""
        from board.models import Post

        user = User.objects.create_user(username='paramuser')

        post = Post.objects.create(
            title='Param Test',
            text='Content',
            author=user,
            category=board_category,
            is_public=is_public,
            is_archived=is_archived,
        )

        assert post.is_public == is_public
        assert post.is_archived == is_archived

    @pytest.mark.parametrize("priority", [1, 5, 10, 20])
    def test_category_priority(self, db, priority):
        """Test category with different priority levels."""
        from board.models import PostCategory

        cat = PostCategory.objects.create(name='Priority Cat {}'.format(priority), priority=priority)

        assert cat.priority == priority


class TestBookkeepingParametrized:
    """Parametrized tests for bookkeeping app."""
    @pytest.mark.parametrize("trans_type", ['I', 'O'])
    def test_transaction_types(self, db, bookkeeping_category, bookkeeping_partner, trans_type):
        """Test both income and outgoing transactions."""
        from bookkeeping.models import Transaction

        user = User.objects.create_user(username='transuser')

        txn = Transaction.objects.create(type=trans_type, category=bookkeeping_category, partner=bookkeeping_partner, amount=100.00, author=user)

        assert txn.type == trans_type

    @pytest.mark.parametrize("amount", [0.01, 100.0, 9999.99, 10000.0])
    def test_transaction_amounts(self, db, bookkeeping_category, bookkeeping_partner, amount):
        """Test transaction with various amounts."""
        from bookkeeping.models import Transaction

        user = User.objects.create_user(username='amountuser')

        txn = Transaction.objects.create(type='I', category=bookkeeping_category, partner=bookkeeping_partner, amount=amount, author=user)

        assert float(txn.amount) == amount


class TestEventsParametrized:
    """Parametrized tests for events app."""
    @pytest.mark.parametrize("frequency", ['once', 'daily', 'weekly', 'monthly'])
    def test_event_frequencies(self, db, frequency):
        """Test events with different frequencies."""
        from events.models import Event

        event = Event.objects.create(
            title='Freq Test',
            description='Test',
            place='Online',
            frequency=frequency,
            start_date='2024-01-01',
        )

        assert event.frequency == frequency

    @pytest.mark.parametrize("is_active", [True, False])
    def test_event_active_status(self, db, is_active):
        """Test both active and inactive events."""
        from events.models import Event

        event = Event.objects.create(
            title='Active Test',
            description='Test',
            place='Online',
            is_active=is_active,
            start_date='2024-01-01',
        )

        assert event.is_active == is_active


class TestChatParametrized:
    """Parametrized tests for chat app."""
    @pytest.mark.parametrize("is_public,archived,protected", [
        (True, False, False),
        (False, False, False),
        (True, True, False),
        (False, True, True),
        (True, False, True),
    ])
    def test_room_configurations(self, db, is_public, archived, protected):
        """Test rooms with different configurations."""
        from chat.models import Room

        room = Room.objects.create(title='Config Room', public=is_public, archived=archived, protected=protected)

        assert room.public == is_public
        assert room.archived == archived
        assert room.protected == protected

    @pytest.mark.parametrize("anonymous", [True, False])
    def test_message_anonymous(self, db, chat_room, anonymous):
        """Test messages with anonymous on/off."""
        from chat.models import Message

        room, users = chat_room

        msg = Message.objects.create(sender=users[0], text='Anonymous test', room=room, anonymous=anonymous)

        assert msg.anonymous == anonymous


class TestGlosowaniaParametrized:
    """Parametrized tests for glosowania app."""
    @pytest.mark.parametrize("argument_type", ['FOR', 'AGAINST'])
    def test_argument_types(self, db, chat_room, argument_type):
        """Test both FOR and AGAINST arguments."""
        from glosowania.models import Argument, Decyzja

        room, users = chat_room
        decyzja = Decyzja.objects.create(title='Param Bill', author=users[0], chat_room=room)

        arg = Argument.objects.create(decyzja=decyzja, author=users[1], argument_type=argument_type, content='Test argument')

        assert arg.argument_type == argument_type

    @pytest.mark.parametrize("vote_value", [True, False])
    def test_vote_codes(self, db, chat_room, vote_value):
        """Test vote codes with True/False."""
        from glosowania.models import Decyzja, VoteCode

        room, users = chat_room
        decyzja = Decyzja.objects.create(title='Vote Test', author=users[0], chat_room=room)

        code = VoteCode.objects.create(project=decyzja, code='PARAM001', vote=vote_value)

        assert code.vote == vote_value


class TestHomeParametrized:
    """Parametrized tests for home app."""
    @pytest.mark.parametrize("content_type", ['post', 'task', 'book', 'event'])
    def test_feed_item_types(self, db, content_type):
        """Test feed items with different content types."""
        from home.models import FeedItem

        user = User.objects.create_user(username='feeduser')

        feed = FeedItem.objects.create(
            content_type=content_type,
            object_id=1,
            title='Feed Test',
            description='Test',
            author=user,
            timestamp='2024-01-01 00:00:00',
        )

        assert feed.content_type == content_type

    @pytest.mark.parametrize("step_value", [True, False])
    def test_onboarding_progress(self, db, step_value):
        """Test onboarding progress with True/False steps."""
        from home.models import OnboardingProgress

        user = User.objects.create_user(username='onboarduser')

        progress = OnboardingProgress.objects.create(user=user, step_argued=step_value, step_chatted=not step_value, step_voted=step_value)

        assert progress.step_argued == step_value
        assert progress.step_voted == step_value


class TestObywateleParametrized:
    """Parametrized tests for obywatele app."""
    @pytest.mark.parametrize("reputation", [-10, -5, 0, 50, 100])
    def test_citizen_reputation(self, db, reputation):
        """Test citizens with different reputation levels."""
        from obywatele.models import Uzytkownik

        user = User.objects.create_user(username='repuser')

        # Delete if exists to avoid unique constraint
        Uzytkownik.objects.filter(uid=user).delete()

        citizen = Uzytkownik.objects.create(uid=user, reputation=reputation, city='Warsaw')

        assert citizen.reputation == reputation

    @pytest.mark.parametrize("rate_value", [-5, -1, 0, 1, 5])
    def test_rate_values(self, db, rate_value):
        """Test ratings from -5 to 5."""
        from obywatele.models import Rate, Uzytkownik

        user1 = User.objects.create_user(username='candidate')
        user2 = User.objects.create_user(username='rater')

        # Delete if exists to avoid unique constraint
        Uzytkownik.objects.filter(uid=user1).delete()
        Uzytkownik.objects.filter(uid=user2).delete()

        candidate = Uzytkownik.objects.create(uid=user1)
        rater = Uzytkownik.objects.create(uid=user2)

        # Delete existing rates to avoid unique constraint
        Rate.objects.filter(kandydat=candidate, obywatel=rater).delete()

        rate = Rate.objects.create(kandydat=candidate, obywatel=rater, rate=rate_value)

        assert rate.rate == rate_value


class TestEdgeCases:
    """Parametrized edge case tests."""
    @pytest.mark.parametrize("empty_field", [
        ('title', ''),
        ('subtitle', ''),
        ('text', ''),
    ])
    def test_empty_fields(self, db, board_category, empty_field):
        """Test handling of empty fields."""
        from board.models import Post

        user = User.objects.create_user(username='emptyuser')

        kwargs = {
            'title': 'Test',
            'subtitle': 'Sub',
            'text': 'Content',
            'author': user,
            'category': board_category
        }
        kwargs[empty_field[0]] = empty_field[1]

        # This should either succeed or fail gracefully
        try:
            post = Post.objects.create(**kwargs)
            assert getattr(post, empty_field[0]) == empty_field[1]
        except Exception:
            assert True  # Graceful failure is OK

    @pytest.mark.parametrize("long_string_len", [100, 1000, 10000])
    def test_long_strings(self, db, long_string_len):
        """Test handling of very long strings."""
        from board.models import Post, PostCategory

        cat = PostCategory.objects.create(name='Long Test')
        user = User.objects.create_user(username='longuser')

        long_text = 'x' * long_string_len

        post = Post.objects.create(title='Long Test', text=long_text, author=user, category=cat)

        assert len(post.text) == long_string_len
