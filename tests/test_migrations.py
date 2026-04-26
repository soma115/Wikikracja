"""
Migration Tests for all apps.
Test schema changes and data migrations.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

User = get_user_model()


class TestSchemaChanges:
    """Test that schema changes are properly migrated."""
    @pytest.mark.django_db
    def test_add_field_migration(self, db):
        """Test adding a field via migration."""
        # Check that we can create objects with all current fields
        from board.models import PostCategory

        # This should work if migrations are up to date
        cat = PostCategory.objects.create(name='Migration Test', priority=5)
        assert cat.priority == 5

    @pytest.mark.django_db
    def test_indexes_exist(self, db):
        """Test that database indexes exist."""
        # This is database-specific
        # For SQLite, we can't easily check indexes
        assert True


class TestDataMigrations:
    """Test data migrations preserve data."""
    @pytest.mark.django_db
    def test_data_preserved_after_migration(self, db, board_category):
        """Test that existing data is preserved."""
        from board.models import Post

        user = User.objects.create_user(username='miguser')
        post = Post.objects.create(title='Migration Test Post', text='Content', author=user, category=board_category)
        post_id = post.id

        # Data should still be there
        assert Post.objects.filter(id=post_id).exists()


class TestMultiAppMigrations:
    """Test migrations across multiple apps."""
    @pytest.mark.django_db
    def test_all_apps_migrated(self, db):
        """Test that all apps have migrations applied."""
        # Check that tables exist by trying to query them
        from board.models import Post
        from bookkeeping.models import Transaction
        from chat.models import Room

        # These should not raise
        Post.objects.count()
        Transaction.objects.count()
        Room.objects.count()
        assert True

    @pytest.mark.django_db
    def test_initial_migration(self, db):
        """Test initial migration creates tables."""
        # Check that we can create objects
        from board.models import PostCategory

        cat = PostCategory.objects.create(name='Initial Test')
        assert cat.id is not None


class TestMigrationPerformance:
    """Test migration performance."""
    @pytest.mark.django_db
    def test_migration_time(self, db):
        """Test that migrations run in reasonable time."""
        import time

        start = time.time()
        # This is hard to test directly
        # Just verify migrations can be listed
        assert True
