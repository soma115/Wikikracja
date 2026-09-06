import pytest
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from board.models import Post
from chat.models import Message, MessageReadBy, Room
from chat.services import CHAT_UNREAD_CACHE_KEY
from core.models import ReadStatus
from core.services import feed as feed_service
from core.services.feed import FEED_CACHE_KEY, generate_feed_items, generate_feed_raw, get_unread_count
from events.models import Event
from glosowania.models import Decyzja
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


@pytest.mark.django_db
@pytest.mark.parametrize('reader_first', [True, False])
def test_private_chat_personalization_does_not_leak_through_shared_cache(feed_user, another_user, reader_first):
    cache.delete(FEED_CACHE_KEY)
    outsider = UserFactory(username='outsider')
    room = Room.objects.create(title='Private shared cache', public=False)
    room.allowed.add(feed_user, another_user)
    message = Message.objects.create(room=room, sender=another_user, text='Private message')
    MessageReadBy.objects.create(message=message, user=feed_user)
    raw = generate_feed_raw()
    users = [feed_user, another_user] if reader_first else [another_user, feed_user]

    for user in [*users, outsider, *users]:
        items = [item for item in generate_feed_items(user) if item['content_type'] == 'room_messages' and item['room_id'] == room.pk]
        if user == outsider:
            assert items == []
            continue
        assert len(items) == 1
        assert items[0]['object_id'] == message.pk
        assert items[0]['title'] == (another_user.username if user == feed_user else feed_user.username)
        assert items[0]['is_read'] is (user == feed_user)
        assert items[0]['url'] == f'/chat/#room_id={room.pk}'
        assert items[0]['message_count'] == 1

    assert generate_feed_raw() == raw
    raw_item = next(item for item in raw if item['content_type'] == 'room_messages' and item['object_id'] == message.pk)
    assert raw_item['title'] == room.title
    assert 'is_read' not in raw_item


@pytest.mark.django_db
def test_private_chat_membership_changes_invalidate_cached_visibility(feed_user, another_user):
    cache.delete(FEED_CACHE_KEY)
    room = Room.objects.create(title='Membership changes', public=False)
    room.allowed.add(feed_user, another_user)
    message = Message.objects.create(room=room, sender=another_user, text='Members only')

    def visible_message_ids():
        return {item['object_id'] for item in generate_feed_items(feed_user) if item['content_type'] == 'room_messages'}

    assert message.pk in visible_message_ids()
    room.allowed.remove(feed_user)
    assert message.pk not in visible_message_ids()
    room.allowed.add(feed_user)
    assert message.pk in visible_message_ids()


@pytest.mark.django_db
@pytest.mark.parametrize(('message_read', 'room_seen'), [(False, False), (True, False), (False, True), (True, True)])
def test_chat_read_state_combines_message_and_room_flags_per_user(feed_user, another_user, message_read, room_seen):
    cache.delete(FEED_CACHE_KEY)
    room = Room.objects.create(title='Read state flags', public=True)
    message = Message.objects.create(room=room, sender=another_user, text='Read state')
    if message_read:
        MessageReadBy.objects.create(message=message, user=feed_user)
    if room_seen:
        room.seen_by.add(feed_user)

    for user in (feed_user, another_user):
        item = next(item for item in generate_feed_items(user) if item['content_type'] == 'room_messages' and item['object_id'] == message.pk)
        assert item['is_read'] is (user == feed_user and (message_read or room_seen))


@pytest.mark.django_db
@pytest.mark.parametrize('content_type', ['room_messages', 'message'])
def test_chat_read_toggle_uses_message_id_and_preserves_other_read_records(feed_user, another_user, content_type):
    cache.delete(FEED_CACHE_KEY)
    room = Room.objects.create(title='Read toggle contract', public=True)
    message = Message.objects.create(pk=room.pk + 100, room=room, sender=another_user, text='First')
    sibling = Message.objects.create(room=room, sender=another_user, text='Second')
    unread_sibling = Message.objects.create(room=room, sender=another_user, text='Third')
    MessageReadBy.objects.create(message=sibling, user=feed_user)
    MessageReadBy.objects.create(message=message, user=another_user)
    room.seen_by.add(another_user)
    unread_cache_key = CHAT_UNREAD_CACHE_KEY.format(user_id=feed_user.pk)

    cache.set(unread_cache_key, 99)
    feed_service.mark_feed_item_as_read(content_type, message.pk, feed_user)
    feed_service.mark_feed_item_as_read(content_type, message.pk, feed_user)
    assert MessageReadBy.objects.filter(message=message, user=feed_user).count() == 1
    assert room.seen_by.filter(pk=feed_user.pk).exists()
    assert cache.get(unread_cache_key) is None
    assert all(item['is_read'] for item in generate_feed_items(feed_user) if item['content_type'] == 'room_messages' and item['room_id'] == room.pk)

    cache.set(unread_cache_key, 99)
    feed_service.mark_feed_item_as_unread(content_type, message.pk, feed_user)
    feed_service.mark_feed_item_as_unread(content_type, message.pk, feed_user)
    assert not MessageReadBy.objects.filter(message=message, user=feed_user).exists()
    assert not room.seen_by.filter(pk=feed_user.pk).exists()
    assert cache.get(unread_cache_key) is None
    assert MessageReadBy.objects.filter(message=sibling, user=feed_user).exists()
    assert MessageReadBy.objects.filter(message=message, user=another_user).exists()
    assert room.seen_by.filter(pk=another_user.pk).exists()
    states = {item['object_id']: item['is_read'] for item in generate_feed_items(feed_user) if item['content_type'] == 'room_messages' and item['room_id'] == room.pk}
    assert states == {message.pk: False, sibling.pk: True, unread_sibling.pk: False}


@pytest.mark.django_db
@pytest.mark.parametrize('anonymous', [False, True])
def test_chat_feed_and_rendered_activity_preserve_message_without_exposing_anonymous_author(feed_user, another_user, rf, anonymous):
    cache.delete(FEED_CACHE_KEY)
    room = Room.objects.create(title='Privacy test room', public=True)
    another_user.uzytkownik.avatar = 'avatars/anonymous-author.png'
    another_user.uzytkownik.save(update_fields=['avatar'])
    message = Message.objects.create(room=room, sender=another_user, anonymous=anonymous, text='Privacy test message')

    raw = next(item for item in generate_feed_raw() if item['content_type'] == 'room_messages' and item['object_id'] == message.pk)
    item = next(item for item in generate_feed_items(feed_user) if item['content_type'] == 'room_messages' and item['object_id'] == message.pk)
    expected_author = None if anonymous else another_user
    assert raw['author'] == item['author'] == expected_author
    assert item['description'] == message.text
    assert item['timestamp'] == message.time
    assert item['url'] == f'/chat/#room_id={room.pk}'
    request = rf.get('/activity/')
    request.user = feed_user
    rendered = render_to_string('home/activity.html', {'feed_items': [item], 'user': feed_user}, request=request)
    assert message.text in rendered
    assert (another_user.username in rendered) is (not anonymous)
    assert ('avatars/anonymous-author.png' in rendered) is (not anonymous)
    message.refresh_from_db()
    assert message.sender_id == another_user.pk


@pytest.mark.django_db
def test_chat_feed_keeps_anonymous_messages_without_a_sender(feed_user):
    cache.delete(FEED_CACHE_KEY)
    room = Room.objects.create(title='Senderless anonymous room', public=True)
    message = Message.objects.create(room=room, sender=None, anonymous=True, text='Anonymous system content')
    item = next(item for item in generate_feed_items(feed_user) if item['content_type'] == 'room_messages' and item['object_id'] == message.pk)
    assert item['author'] is None
    assert item['description'] == message.text


@pytest.mark.django_db
def test_chat_feed_does_not_reuse_legacy_cache_with_exposed_author(feed_user, another_user):
    cache.delete(FEED_CACHE_KEY)
    room = Room.objects.create(title='Legacy privacy cache', public=True)
    message = Message.objects.create(room=room, sender=another_user, anonymous=True, text='Legacy anonymous content')
    legacy = {'content_type': 'room_messages', 'object_id': message.pk, 'room_id': room.pk, 'title': room.title, 'author': another_user, 'timestamp': message.time, '_is_public': True}
    cache.set('feed_raw_v2', [legacy])
    try:
        item = next(item for item in generate_feed_items(feed_user) if item['content_type'] == 'room_messages' and item['object_id'] == message.pk)
        assert item['author'] is None
        assert item['description'] == message.text
    finally:
        cache.delete('feed_raw_v2')
        cache.delete(FEED_CACHE_KEY)
