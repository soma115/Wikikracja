import pytest
from django.utils import timezone

from bookkeeping.models import Asset
from glosowania.models import Decyzja
from home.models import ReadStatus
from home.services.dashboard import build_dashboard_context
from tests.factories import UserFactory


@pytest.fixture
def dashboard_user(db):
    return UserFactory(username='dashboard', email='dashboard@example.com')


@pytest.mark.django_db
def test_dashboard_default_asset_none(dashboard_user):
    Asset.objects.all().delete()
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
    assert ctx['active_referendum']['obj'] == decision
    assert ctx['active_referendum']['bar_color'] == 'success'

    # 20-50% -> warning
    decision.data_referendum_start = today - timezone.timedelta(days=6)
    decision.data_referendum_stop = today + timezone.timedelta(days=4)
    decision.save()
    ctx = build_dashboard_context(dashboard_user)
    assert ctx['active_referendum']['bar_color'] == 'warning'

    # < 20% -> danger
    decision.data_referendum_start = today - timezone.timedelta(days=9)
    decision.data_referendum_stop = today + timezone.timedelta(days=1)
    decision.save()
    ctx = build_dashboard_context(dashboard_user)
    assert ctx['active_referendum']['bar_color'] == 'danger'


@pytest.mark.django_db
def test_dashboard_no_active_referendum(dashboard_user):
    ctx = build_dashboard_context(dashboard_user)
    assert ctx['active_referendum'] is None


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
