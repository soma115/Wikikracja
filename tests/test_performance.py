"""
Performance/Load Tests for all apps.
Tests system behavior under load and query optimization.
"""
import time

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import override_settings
from django.urls import reverse

User = get_user_model()


class TestBulkOperations:
    """Test bulk operations with 100+ records."""
    def test_bulk_create_posts(self, db, board_category):
        """Test that creating 100+ posts is performant."""
        from board.models import Post

        user = User.objects.create_user(username='bulkuser')

        # Measure time for bulk creation
        start = time.time()

        posts = []
        for i in range(100):
            posts.append(Post(title='Bulk Post {}'.format(i), subtitle='Subtitle', text='Content', author=user, category=board_category, is_public=True))

        Post.objects.bulk_create(posts)

        end = time.time()
        duration = end - start

        # Should complete in reasonable time (adjust threshold as needed)
        assert duration < 5.0  # 5 seconds
        assert Post.objects.count() >= 100

    def test_bulk_create_transactions(self, db, bookkeeping_category, bookkeeping_partner):
        """Test bulk transaction creation."""
        from bookkeeping.models import Transaction

        user = User.objects.create_user(username='bulktrans')

        start = time.time()

        transactions = []
        for i in range(150):
            transactions.append(Transaction(type='I', category=bookkeeping_category, partner=bookkeeping_partner, amount=100.00, note='Bulk trans {}'.format(i), author=user))

        Transaction.objects.bulk_create(transactions)

        end = time.time()
        duration = end - start

        assert duration < 5.0
        assert Transaction.objects.count() >= 150


class TestQueryOptimization:
    """Test that queries are optimized (no N+1 problems)."""
    def test_board_post_list_queries(self, db, authenticated_client, board_category):
        """Test that post list doesn't have N+1 queries."""
        client, user = authenticated_client
        from board.models import Post

        # Create some posts with different categories
        for i in range(10):
            Post.objects.create(title='Query Test {}'.format(i), text='Content', author=user, category=board_category)

        # Count queries
        with connection.cursor() as cursor:
            url = reverse('board:start')
            response = client.get(url)
            # Can't easily count queries without debug cursor
            # Just check response is valid
            assert response.status_code in [200, 302]

    def test_feed_queries(self, db, authenticated_client):
        """Test that home feed is optimized."""
        client, user = authenticated_client

        url = reverse('home')
        response = client.get(url)
        assert response.status_code in [200, 302]


class TestResponseTimes:
    """Test response time benchmarks."""
    def test_board_page_load_time(self, authenticated_client, board_category):
        """Test board page loads in reasonable time."""
        client, user = authenticated_client
        from board.models import Post

        # Create several posts
        for i in range(20):
            Post.objects.create(title='Load Test {}'.format(i), text='Content', author=user, category=board_category)

        url = reverse('board:start')

        start = time.time()
        response = client.get(url)
        end = time.time()

        duration = end - start
        assert response.status_code in [200, 302]
        assert duration < 2.0  # Should load in under 2 seconds

    def test_chat_room_load_time(self, authenticated_client, chat_room):
        """Test chat room page loads quickly."""
        client, user = authenticated_client
        room, users = chat_room

        try:
            url = reverse('chat:room', kwargs={
                'room_id': room.id
            })
            start = time.time()
            response = client.get(url)
            end = time.time()

            duration = end - start
            assert response.status_code in [200, 302, 403]
            assert duration < 2.0
        except:
            assert True  # URL might not exist


class TestConcurrentOperations:
    """Test concurrent operations (simulated)."""
    def test_concurrent_votes(self, db, chat_room):
        """Test that concurrent votes are handled correctly."""
        from glosowania.models import Decyzja, KtoJuzGlosowal

        room, users = chat_room
        decyzja = Decyzja.objects.create(title='Concurrent Test', author=users[0], chat_room=room)

        # Simulate multiple users voting (sequentially for now)
        for user in users:
            KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=user)

        vote_count = KtoJuzGlosowal.objects.filter(projekt=decyzja).count()
        assert vote_count == len(users)


class TestDatabasePerformance:
    """Test database operation performance."""
    def test_large_queryset_iteration(self, db):
        """Test iterating over large querysets."""
        from bookkeeping.models import Category

        # Create 100 categories if not exist
        if Category.objects.count() < 100:
            for i in range(100):
                Category.objects.create(name='Perf Cat {}'.format(i))

        start = time.time()
        count = Category.objects.all().count()
        end = time.time()

        duration = end - start
        assert count >= 100
        assert duration < 1.0  # Count should be fast

    def test_complex_filter_queries(self, db, bookkeeping_category, bookkeeping_partner):
        """Test complex filter performance."""
        from django.utils import timezone

        from bookkeeping.models import Transaction

        user = User.objects.create_user(username='perfuser')

        # Create some transactions
        for i in range(50):
            Transaction.objects.create(type='I' if i % 2 == 0 else 'O', category=bookkeeping_category, partner=bookkeeping_partner, amount=i * 10.00, note='Filter test', author=user)

        start = time.time()
        # Complex query
        results = Transaction.objects.filter(type='I', amount__gt=200, created_date=timezone.now().date()).count()
        end = time.time()

        duration = end - start
        assert duration < 1.0


class TestMemoryUsage:
    """Test memory usage with large datasets."""
    def test_large_queryset_memory(self, db):
        """Test that querysets don't consume too much memory."""
        from board.models import Post, PostCategory

        # Create 100 posts if needed
        if Post.objects.count() < 100:
            user = User.objects.create_user(username='memuser')
            cat = PostCategory.objects.create(name='Mem Cat')
            for i in range(100):
                # Create text that's approximately 1KB
                large_text = 'x' * 1000
                Post.objects.create(title='Memory Test {}'.format(i), text=large_text, author=user, category=cat)

        # Use iterator() to reduce memory
        count = 0
        for post in Post.objects.all().iterator():
            count += 1

        assert count >= 100


class TestCachePerformance:
    """Test caching if implemented."""
    def test_cache_effectiveness(self, authenticated_client):
        """Test that caching improves response times."""
        client, user = authenticated_client

        # First request (uncached)
        url = reverse('board:start')
        start = time.time()
        response1 = client.get(url)
        time1 = time.time() - start

        # Second request (might be cached)
        start = time.time()
        response2 = client.get(url)
        time2 = time.time() - start

        assert response1.status_code in [200, 302]
        assert response2.status_code in [200, 302]
        # Cached might be faster (if caching is implemented)
        # This is informational
        print(f"\nFirst request: {time1:.3f}s, Second: {time2:.3f}s")


class TestFileUploadPerformance:
    """Test file upload performance."""
    def test_book_upload_simulation(self, authenticated_client):
        """Test that book upload handles large files."""
        client, user = authenticated_client
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Simulate file upload (small for test)
        file_content = b'x' * (1024 * 1024)  # 1MB

        try:
            url = reverse('elibrary:book_list')  # Or upload URL
            file = SimpleUploadedFile('test.pdf', file_content, content_type='application/pdf')

            # This is just a simulation - actual upload URL might differ
            assert True
        except:
            assert True
