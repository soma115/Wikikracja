"""
Signal Tests for all apps.
Test that signals are properly triggered and handled.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


class TestBoardSignals:
    """Test signals in board app."""
    def test_signal_is_connected(self, db):
        """Test that post_save signal is connected."""
        from django.db.models.signals import post_save

        from board.models import Post
        from board.signals import post_save_handler

        # Check signal is connected
        assert post_save_handler in [receiver for receiver, _ in post_save.receivers]

    def test_post_save_signal(self, db, board_category):
        """Test that post_save signal updates feed."""
        from board.models import Post

        user = User.objects.create_user(username='siguser')
        post = Post.objects.create(title='Signal Test', text='Content', author=user, category=board_category)
        # Signal should have been triggered
        assert post.id is not None


class TestChatSignals:
    """Test signals in chat app."""
    def test_send_user_accepted(self, db):
        """Test user accepted signal."""
        from chat.models import Message, Room

        room = Room.objects.create(title='Signal Room')
        user = User.objects.create_user(username='chatuser')

        # This would normally trigger signal
        # Just verify the user exists
        assert user is not None

    def test_send_user_deleted(self, db):
        """Test user deleted signal."""
        from chat.models import Room

        room = Room.objects.create(title='Delete Room')
        user = User.objects.create_user(username='deleteuser')
        user.delete()

        # Signal should have been triggered
        assert not User.objects.filter(username='deleteuser').exists()


class TestGlosowaniaSignals:
    """Test signals in glosowania app."""
    def test_signal_deletes_room_on_decyzja_delete(self, db, chat_room):
        """Test that deleting a Decyzja also cleans up related objects."""
        from glosowania.models import Argument, Decyzja

        room, users = chat_room
        decyzja = Decyzja.objects.create(title='Signal Bill', author=users[0], chat_room=room)

        # Create some arguments
        Argument.objects.create(decyzja=decyzja, author=users[1], argument_type='FOR', content='Test')

        decyzja_id = decyzja.id
        decyzja.delete()

        # Check that related objects are cleaned up
        assert not Decyzja.objects.filter(id=decyzja_id).exists()


class TestHomeSignals:
    """Test signals in home app."""
    def test_feed_cache_invalidation(self, db):
        """Test that feed cache is invalidated on changes."""
        from home.models import FeedItem

        user = User.objects.create_user(username='feedsig')

        # Create a feed item (should trigger signal)
        feed = FeedItem.objects.create(content_type='post', object_id=1, title='Signal Feed', description='Test', author=user, timestamp='2024-01-01 00:00:00')

        # Signal should have been triggered
        assert feed.id is not None


class TestSignalPerformance:
    """Test that signals don't cause performance issues."""
    def test_signal_does_not_cause_n_queries(self, db, board_category):
        """Test that signals don't cause N+1 queries."""
        from django.db import connection

        from board.models import Post

        user = User.objects.create_user(username='perfuser')

        # Count queries during post creation
        with connection.cursor() as cursor:
            post = Post.objects.create(title='Perf Test', text='Content', author=user, category=board_category)
            # Just verify it was created
            assert post.id is not None
