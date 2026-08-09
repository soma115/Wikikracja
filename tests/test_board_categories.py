"""Testy usuwania kategorii dokumentów (board) bez wymuszania reassignmentu.

Regresja głównego buga: kategoria używana przez dokumenty MUSI dać się usunąć — FK
`Post.category` ma `on_delete=SET_NULL`, więc dokumenty stają się nieskategoryzowane.
Plus generyczny endpoint listy elementów kategorii (tytuły + count, z limitem).
"""

import pytest
from django.urls import reverse

from tests.factories import PostCategoryFactory, PostFactory


@pytest.mark.django_db
def test_delete_category_in_use_unassigns_documents(authenticated_client):
    """DELETE kategorii używanej przez dokumenty → 200; dokumenty zostają bez kategorii."""
    from board.models import Post, PostCategory

    client, _ = authenticated_client
    cat = PostCategoryFactory()
    posts = PostFactory.create_batch(3, category=cat)

    res = client.post(reverse('board:api_category_delete', args=[cat.pk]))

    assert res.status_code == 200
    assert not PostCategory.objects.filter(pk=cat.pk).exists()
    for post in posts:
        post.refresh_from_db()
        assert post.category_id is None
    assert Post.objects.filter(pk__in=[p.pk for p in posts]).count() == 3


@pytest.mark.django_db
def test_delete_protected_category_blocked(authenticated_client):
    """DELETE kategorii is_protected → 403; kategoria nadal istnieje."""
    from board.models import PostCategory

    client, _ = authenticated_client
    cat = PostCategoryFactory(is_protected=True)

    res = client.post(reverse('board:api_category_delete', args=[cat.pk]))

    assert res.status_code == 403
    assert PostCategory.objects.filter(pk=cat.pk).exists()


@pytest.mark.django_db
def test_category_items_returns_titles_and_count_with_limit(authenticated_client):
    """GET items → tytuły powiązanych dokumentów + pełny count; respektuje limit."""
    from board.views import PostCategoryItemsAPI

    client, _ = authenticated_client
    cat = PostCategoryFactory()
    limit = PostCategoryItemsAPI.limit
    total = limit + 5
    PostFactory.create_batch(total, category=cat)

    res = client.get(reverse('board:api_category_items', args=[cat.pk]))

    assert res.status_code == 200
    data = res.json()
    assert data['count'] == total
    assert len(data['items']) == limit
    # deterministyczny podgląd: zwrócone tytuły to pierwsze `limit` posortowanych alfabetycznie
    all_titles = sorted(cat.posts.values_list('title', flat=True))
    assert data['items'] == all_titles[:limit]


@pytest.mark.django_db
def test_category_items_requires_login(client):
    """Niezalogowany GET items → redirect (LoginRequiredMixin)."""
    cat = PostCategoryFactory()

    res = client.get(reverse('board:api_category_items', args=[cat.pk]))

    assert res.status_code in (302, 403)
