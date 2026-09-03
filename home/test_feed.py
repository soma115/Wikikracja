import pytest
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags

from board.models import Post
from chat.models import Message, Room
from events.models import Event
from glosowania.models import Decyzja
from home.models import ReadStatus
from home.services import feed as feed_service
from home.services.feed import FEED_CACHE_KEY, generate_feed_items, generate_feed_raw, get_unread_count
from tasks.models import Task
from tests.factories import PostCategoryFactory, PostFactory, UserFactory


@pytest.fixture
def another_user(db):
    return UserFactory(username='another', email='another@example.com')


@pytest.fixture
def feed_user(db):
    return UserFactory(username='feeduser', email='feed@example.com')


def _feed_titles(raw_items):
    return [i['title'] for i in raw_items]


@pytest.mark.django_db
def test_generate_feed_raw_sorts_events_ascending_others_descending(feed_user, another_user):
    cache.delete(FEED_CACHE_KEY)

    category = PostCategoryFactory()
    # Post updated in the past
    post = PostFactory(author=feed_user, category=category, title='Post A', text='Post body')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now() - timezone.timedelta(days=1))

    # Decision updated now
    Decyzja.objects.create(title='Decision Z', tresc='Content', author=feed_user, status=Decyzja.Status.PROPOSITION)

    # Event in the future (events sort ascending by next occurrence)
    Event.objects.create(title='Event M', description='Description', start_date=timezone.now() + timezone.timedelta(days=2), frequency='once', is_active=True)

    # Task updated two days ago
    task = Task.objects.create(title='Task B', description='Task body', created_by=feed_user, assigned_to=another_user, status=Task.Status.ACTIVE)
    Task.objects.filter(pk=task.pk).update(updated_at=timezone.now() - timezone.timedelta(days=2))

    items = generate_feed_raw()

    # Events come first, then non-events sorted by timestamp descending
    content_types = [i['content_type'] for i in items]
    assert content_types[0] == 'event'

    non_event_titles = _feed_titles([i for i in items if i['content_type'] != 'event'])
    # The three fixtures above should appear in this order (newest first), ignoring
    # pre-existing seeded posts/citizen activities.
    assert non_event_titles.index('Decision Z') < non_event_titles.index('Post A')
    assert non_event_titles.index('Post A') < non_event_titles.index('Task B')


@pytest.mark.django_db
def test_feed_description_truncation(feed_user):
    cache.delete(FEED_CACHE_KEY)
    category = PostCategoryFactory()
    long_text = 'word ' * 100  # > 125 chars
    post = PostFactory(author=feed_user, category=category, title='Long', text=f'<p>{long_text}</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    raw = generate_feed_raw()
    post_item = next(i for i in raw if i['content_type'] == 'post' and i['object_id'] == post.pk)
    clean = strip_tags(long_text)
    assert post_item['description'] == clean[:125] + '...'


@pytest.mark.django_db
def test_feed_raw_cache_hit_and_miss(feed_user):
    cache.delete(FEED_CACHE_KEY)
    category = PostCategoryFactory()
    first_post = PostFactory(author=feed_user, category=category, title='First', text='<p>first</p>')
    Post.objects.filter(pk=first_post.pk).update(updated=timezone.now())

    first = generate_feed_raw()
    assert any(i['object_id'] == first_post.pk for i in first)

    # Cache hit returns the cached value verbatim
    cached_value = [{'content_type': 'post', 'object_id': 999, 'timestamp': timezone.now()}]
    cache.set(FEED_CACHE_KEY, cached_value, 3600)
    second = generate_feed_raw()
    assert second == cached_value

    cache.delete(FEED_CACHE_KEY)
    third = generate_feed_raw()
    assert any(i['object_id'] == first_post.pk for i in third)


@pytest.mark.django_db
def test_generate_feed_items_filters_private_rooms(feed_user, another_user):
    cache.delete(FEED_CACHE_KEY)

    public_room = Room.objects.create(title='Public', public=True)
    Message.objects.create(room=public_room, sender=feed_user, text='Hello public')

    private_room = Room.objects.create(title='Private', public=False)
    private_room.allowed.add(another_user)
    Message.objects.create(room=private_room, sender=another_user, text='Secret')

    items = generate_feed_items(feed_user)
    room_items = [i for i in items if i['content_type'] == 'room_messages']
    public_item = next((i for i in room_items if 'Public' in i['title']), None)
    private_item = next((i for i in room_items if 'Private' in i['title']), None)

    assert public_item is not None
    assert private_item is None


@pytest.mark.django_db
def test_get_unread_count_uses_readstatus(feed_user):
    cache.delete(FEED_CACHE_KEY)
    category = PostCategoryFactory()
    post = PostFactory(author=feed_user, category=category, title='Read me', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    before = get_unread_count(feed_user)
    ReadStatus.objects.create(user=feed_user, content_type=ReadStatus.ContentType.POST, object_id=post.pk)
    after = get_unread_count(feed_user)
    assert after == before - 1


@pytest.mark.django_db
def test_mark_feed_item_as_read_and_unread_for_post(feed_user):
    cache.delete(FEED_CACHE_KEY)
    category = PostCategoryFactory()
    post = PostFactory(author=feed_user, category=category, title='Mark me', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    before = get_unread_count(feed_user)
    feed_service.mark_feed_item_as_read('post', post.pk, feed_user)
    assert get_unread_count(feed_user) == before - 1
    feed_service.mark_feed_item_as_unread('post', post.pk, feed_user)
    assert get_unread_count(feed_user) == before


@pytest.mark.django_db
def test_mark_feed_item_as_read_and_unread_for_chat(feed_user, another_user):
    cache.delete(FEED_CACHE_KEY)
    room = Room.objects.create(title='Markable', public=False)
    room.allowed.add(feed_user)
    Message.objects.create(room=room, sender=another_user, text='Hi')

    before = get_unread_count(feed_user)
    message = Message.objects.get(room=room)
    feed_service.mark_feed_item_as_read('room_messages', message.pk, feed_user)
    assert get_unread_count(feed_user) == before - 1
    feed_service.mark_feed_item_as_unread('room_messages', message.pk, feed_user)
    assert get_unread_count(feed_user) == before


@pytest.mark.django_db
def test_mark_all_feed_items_as_read(feed_user, another_user):
    cache.delete(FEED_CACHE_KEY)
    category = PostCategoryFactory()
    post = PostFactory(author=feed_user, category=category, title='Mark all', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    room = Room.objects.create(title='All chat', public=False)
    room.allowed.add(feed_user)
    Message.objects.create(room=room, sender=another_user, text='Hi')

    before = get_unread_count(feed_user)
    count = feed_service.mark_all_feed_items_as_read(feed_user)
    assert count == before
    assert get_unread_count(feed_user) == 0
