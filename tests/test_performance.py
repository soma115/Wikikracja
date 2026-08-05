"""Performance testy bulk_create — wykrywają N+1 query patterns.

Asercja na liczbie zapytań (CaptureQueriesContext), nie na czasie wykonania —
czas w SQLite testowej jest zbyt zmienny i nigdy nie wykryje N+1 w sensownym progu.
N+1 dla bulk_create(100) dałoby 100+ INSERT queries; poprawny bulk_create wykonuje 1-2.
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.factories import UserFactory


@pytest.mark.django_db
def test_bulk_create_posts_uses_minimal_queries(board_category):
    """bulk_create 100 postów wykonuje ≤ 5 zapytań (regresja na N+1 dałaby 100+)."""
    from board.models import Post

    user = UserFactory()
    posts = [Post(title=f'Bulk {i}', subtitle='Sub', text=f'<p>{i}</p>', author=user, category=board_category, is_public=True) for i in range(100)]

    with CaptureQueriesContext(connection) as ctx:
        Post.objects.bulk_create(posts)

    query_count = len(ctx.captured_queries)
    assert query_count <= 5, f'bulk_create 100 posts wykonał {query_count} zapytań — możliwy N+1 lub utrata bulk semantyki'
    assert Post.objects.filter(title__startswith='Bulk ').count() == 100


@pytest.mark.django_db
def test_bulk_create_transactions_uses_minimal_queries(bookkeeping_category, bookkeeping_partner):
    """bulk_create 150 transakcji wykonuje ≤ 5 zapytań."""
    from bookkeeping.models import Transaction

    user = UserFactory()
    from bookkeeping.models import Asset
    asset = Asset.get_default()
    transactions = [Transaction(type='I', category=bookkeeping_category, partner=bookkeeping_partner, asset=asset, amount=100.00, note=f'Bulk {i}', author=user) for i in range(150)]

    with CaptureQueriesContext(connection) as ctx:
        Transaction.objects.bulk_create(transactions)

    query_count = len(ctx.captured_queries)
    assert query_count <= 5, f'bulk_create 150 transactions wykonał {query_count} zapytań — możliwy N+1'
    assert Transaction.objects.filter(note__startswith='Bulk ').count() == 150
