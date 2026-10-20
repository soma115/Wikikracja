import tempfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import ReadStatus
from glosowania.models import Decyzja
from home.services.dashboard import build_dashboard_context
from resources.models import Entity
from site_settings.models import QuickLink
from tests.factories import UserFactory


@pytest.fixture
def dashboard_user(db):
    return UserFactory(username='dashboard', email='dashboard@example.com')


@pytest.mark.django_db
def test_dashboard_default_asset_none(dashboard_user):
    Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET).delete()
    Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET).delete()
    ctx = build_dashboard_context(dashboard_user)
    assert ctx['default_asset'] is None
    assert ctx['default_income'] is None
    assert ctx['default_expenses'] is None
    assert ctx['default_balance'] is None
    assert ctx['default_symbol'] is None


@pytest.mark.django_db
def test_dashboard_active_referendum_bar_colors(dashboard_user):
    today = timezone.now().date()
    # > 50% remaining -> success
    decision = Decyzja.objects.create(
        title='Active referendum',
        tresc='Content',
        author=dashboard_user,
        status=Decyzja.Status.REFERENDUM,
        data_referendum_start=today - timezone.timedelta(days=4),
        data_referendum_stop=today + timezone.timedelta(days=6),
    )
    ctx = build_dashboard_context(dashboard_user)
    referendum_item = ctx['voting_items'][0]
    assert referendum_item['obj'] == decision
    assert referendum_item['meta']['bar_color'] == 'success'

    # 20-50% -> warning
    decision.data_referendum_start = today - timezone.timedelta(days=6)
    decision.data_referendum_stop = today + timezone.timedelta(days=4)
    decision.save()
    ctx = build_dashboard_context(dashboard_user)
    referendum_item = ctx['voting_items'][0]
    assert referendum_item['meta']['bar_color'] == 'warning'

    # < 20% -> danger
    decision.data_referendum_start = today - timezone.timedelta(days=9)
    decision.data_referendum_stop = today + timezone.timedelta(days=1)
    decision.save()
    ctx = build_dashboard_context(dashboard_user)
    referendum_item = ctx['voting_items'][0]
    assert referendum_item['meta']['bar_color'] == 'danger'


@pytest.mark.django_db
def test_dashboard_no_active_referendum(dashboard_user):
    ctx = build_dashboard_context(dashboard_user)
    assert not any(item['type'] == 'referendum' for item in ctx['voting_items'])


@pytest.mark.django_db
def test_dashboard_feed_filter_unread(dashboard_user):
    from board.models import Post

    post = Post.objects.create(title='Unread post', text='<p>body</p>', author=dashboard_user)

    ctx_all = build_dashboard_context(dashboard_user, filter_unread=False)
    assert any(i['object_id'] == post.pk for i in ctx_all['feed_items'])

    ctx_unread = build_dashboard_context(dashboard_user, filter_unread=True)
    assert any(i['object_id'] == post.pk for i in ctx_unread['feed_items'])
    assert ctx_unread['filter_unread'] is True

    # Mark as read
    ReadStatus.objects.create(user=dashboard_user, content_type=ReadStatus.ContentType.POST, object_id=post.pk)
    ctx_unread_after = build_dashboard_context(dashboard_user, filter_unread=True)
    assert not any(i['object_id'] == post.pk for i in ctx_unread_after['feed_items'])


@pytest.mark.django_db
def test_dashboard_featured_documents(dashboard_user):
    from board.models import Post

    post_without = Post.objects.create(title='No image', text='<p>body</p>', author=dashboard_user)
    image = SimpleUploadedFile('featured.png', b'x', content_type='image/png')

    with tempfile.TemporaryDirectory() as tmp:
        with override_settings(MEDIA_ROOT=tmp):
            post_with = Post.objects.create(title='With image', text='<p>body</p>', author=dashboard_user, featured_image=image)

            ctx = build_dashboard_context(dashboard_user)
            featured = list(ctx['featured_documents'])

            assert post_with in featured
            assert post_without not in featured
            assert ctx['featured_documents'].ordered


@pytest.mark.django_db
def test_home_renders_featured_documents_tile(dashboard_user, client):
    from board.models import Post

    image = SimpleUploadedFile('featured.png', b'x', content_type='image/png')

    with tempfile.TemporaryDirectory() as tmp:
        with override_settings(MEDIA_ROOT=tmp):
            Post.objects.create(title='Featured doc', text='<p>body</p>', author=dashboard_user, featured_image=image)
            client.force_login(dashboard_user)
            response = client.get('/')
            content = response.content.decode()

            assert response.status_code == 200
            assert 'featured-docs-carousel' in content
            assert 'Featured doc' in content


@pytest.mark.django_db
def test_home_renders_community_map_tile_with_member_visibility(dashboard_user, client):
    QuickLink.objects.create(title='Test link', url='/help/', order=0)
    client.force_login(dashboard_user)
    response = client.get('/')
    content = response.content.decode()

    assert response.status_code == 200
    assert 'class="tw-dashboard-tile tw-dashboard-tile--1x1" data-tile-id="community-map"' in content
    assert 'tw-z-[700]' in content
    assert content.index('data-tile-id="onboarding"') < content.index('data-tile-id="activity"')
    assert content.index('data-tile-id="activity"') < content.index('data-tile-id="community-map"')
    assert content.index('data-tile-id="community-map"') < content.index('data-tile-id="upcoming-events"')
    assert f'data-map-data-url="{reverse("obywatele:mapa_data")}"' in content
    assert f'data-map-full-url="{reverse("obywatele:mapa")}"' in content
    assert f'href="{reverse("obywatele:mapa")}" class="tw-sr-only"' in content
    assert 'data-map-member="true"' in content
    assert 'data-map-display-only="true"' in content
    assert 'data-map-details=' not in content
    assert 'data-map-error=' not in content
    assert 'id="community-map-empty"' not in content
    assert 'id="community-map-unmapped"' not in content
    assert 'id="community-map-status"' not in content
    assert 'obywatele/js/community-map.js' in content


@pytest.mark.django_db
def test_group_settings_uses_public_name_and_handles_invalid_reorder(dashboard_user, client):
    client.force_login(dashboard_user)

    response = client.get(reverse('group_settings'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Ustawienia grup' in content or 'Ustawienia grupy' in content or 'Group settings' in content
    assert 'Administracja strony i ustawień globalnych' not in content

    legacy = client.get('/site-settings/')
    assert legacy.status_code == 301
    assert legacy.url.endswith('/ustawienia-grupy/')

    before_count = QuickLink.objects.count()
    invalid = client.post(reverse('group_settings'), {'reorder_quick_links': '1', 'order': '{invalid'})
    assert invalid.status_code == 400
    assert QuickLink.objects.count() == before_count
