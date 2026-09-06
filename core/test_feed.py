from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.cache import cache
from django.utils import timezone

from chat.models import Message, MessageReadBy, Room
from core import feed_registry
from core.feed_registry import DIGEST_GROUP_ID, get_provider, register_feed_provider
from core.models import ReadStatus
from core.services import feed

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username='feed-viewer')


@pytest.fixture(autouse=True)
def isolate_feed(monkeypatch):
    monkeypatch.setattr(feed_registry, '_providers', feed_registry._providers.copy())
    cache.delete(feed.FEED_CACHE_KEY)
    yield
    cache.delete(feed.FEED_CACHE_KEY)


def row(content_type, object_id, title, timestamp):
    return {'content_type': content_type, 'object_id': object_id, 'title': title, 'timestamp': timestamp}


def test_normal_preparation_batches_interleaved_rows_without_reordering(user, monkeypatch):
    now = timezone.now()
    raw = [row(ct, oid, title, now) for ct, oid, title in [('custom', 7, 'first'), ('post', 7, 'read'), ('custom', 7, 'hidden'), ('task', 7, 'unread'), ('custom', 7, 'last'), ('unknown', 7, 'unknown')]]
    original = deepcopy(raw)
    ReadStatus.objects.create(user=user, content_type='post', object_id=7)

    def prepare(items, viewer):
        assert viewer == user
        assert items == [original[0], original[2], original[4]]
        for item in items:
            item['is_read'] = True
            item['title'] += ' prepared'
        return [items[0], None, items[2]]

    callback = Mock(side_effect=prepare)
    register_feed_provider('custom', get_items=lambda since: [], prepare_items=callback)
    assert get_provider('post').prepare_items is None
    assert get_provider('task').prepare_items is None
    monkeypatch.setattr(feed, 'generate_feed_raw', lambda: raw)
    cache.set(feed.FEED_CACHE_KEY, raw)
    result = feed.generate_feed_items(user)
    assert [item['title'] for item in result] == ['first prepared', 'read', 'unread', 'last prepared', 'unknown']
    assert [item['is_read'] for item in result] == [True, True, False, True, False]
    assert result[1] == {**original[1], 'is_read': True}
    assert result[2] == {**original[3], 'is_read': False}
    callback.assert_called_once()
    assert raw == original == cache.get(feed.FEED_CACHE_KEY)


def test_digest_preparation_groups_by_private_key_and_counts_source_rows(user, monkeypatch):
    now = timezone.now()
    since = now - timedelta(days=1)
    raw = [row(ct, oid, title, now) for ct, oid, title in [('custom', 7, 'first'), ('post', 7, 'post'), ('custom', 8, 'hidden'), ('custom', 9, 'second'), ('post', 7, 'post again'), ('custom', 7, 'separate')]]
    original = deepcopy(raw)

    def prepare(items, viewer, cutoff):
        assert viewer == user and cutoff == since
        assert items == [original[i] for i in (0, 2, 3, 5)]
        for item, group in zip(items, ('shared', 'shared', 'shared', 'separate'), strict=True):
            item[DIGEST_GROUP_ID] = group
            item['update_count'] = 99
        return [items[0], None, items[2], items[3]]

    callback = Mock(side_effect=prepare)
    register_feed_provider('custom', get_items=lambda since: [], prepare_digest_items=callback)
    assert get_provider('post').prepare_digest_items is None
    monkeypatch.setattr(feed, 'collect_feed_items', lambda cutoff: raw)
    cache.set(feed.FEED_CACHE_KEY, raw)
    result = feed.build_user_digest(user, since)
    assert result == [{**original[0], 'update_count': 2}, {**original[1], 'update_count': 2}, {**original[5], 'update_count': 1}]
    assert all(DIGEST_GROUP_ID not in item for item in result)
    callback.assert_called_once()
    assert raw == original == cache.get(feed.FEED_CACHE_KEY)


@pytest.mark.parametrize('digest', [False, True])
@pytest.mark.parametrize('output_length', [0, 1, 3])
def test_preparation_rejects_misaligned_output(user, monkeypatch, digest, output_length):
    now = timezone.now()
    raw = [row('custom', 7, 'first', now), row('custom', 7, 'second', now)]
    callback = Mock(return_value=[raw[0].copy() for _ in range(output_length)])
    hook = 'prepare_digest_items' if digest else 'prepare_items'
    register_feed_provider('custom', get_items=lambda since: raw, **{hook: callback})
    monkeypatch.setattr(feed, 'generate_feed_raw', lambda: raw)
    monkeypatch.setattr(feed, 'collect_feed_items', lambda since: raw)
    with pytest.raises(ValueError):
        feed.build_user_digest(user, now - timedelta(days=1)) if digest else feed.generate_feed_items(user)
    callback.assert_called_once()


@pytest.fixture
def chat_batch(user, django_user_model):
    other = django_user_model.objects.create_user(username='feed-other')
    outsider = django_user_model.objects.create_user(username='feed-outsider')
    private = Room.objects.create(title='feed-private', public=False)
    private.allowed.add(user, other)
    public = Room.objects.create(title='feed-public', public=True)
    hidden = Room.objects.create(title='feed-hidden', public=False)
    hidden.allowed.add(outsider)
    own = Room.objects.create(title='feed-own', public=True)
    since = timezone.now() - timedelta(hours=1)
    messages = []
    for room in (private, public, hidden, own):
        for index in range(5):
            sender = user if room == own or (room in (private, public) and index == 4) else other
            message = Message.objects.create(room=room, sender=sender, text=f'{room.title}-{index}')
            Message.objects.filter(pk=message.pk).update(time=since + timedelta(minutes=index + 1))
            messages.append(message)
    MessageReadBy.objects.create(user=user, message=messages[0])
    MessageReadBy.objects.create(user=other, message=messages[1])
    public.seen_by.add(user)
    provider = get_provider('room_messages')
    raw = provider.get_items(since)
    ids = {message.pk for message in messages}
    raw = [item for item in raw if item['object_id'] in ids]
    raw.sort(key=lambda item: item['object_id'])
    return user, other, private, public, own, since, raw, messages


@pytest.mark.parametrize('size', [1, 20])
@pytest.mark.parametrize('viewer_index', [0, 1])
@pytest.mark.parametrize('digest', [False, True])
def test_chat_hooks_batch_queries_and_preserve_raw(chat_batch, django_assert_num_queries, size, viewer_index, digest):
    user, other, private, public, own, since, all_raw, messages = chat_batch
    viewer = (user, other)[viewer_index]
    raw = all_raw[:size]
    original = deepcopy(raw)
    expected = []
    for item in raw:
        if not item['_is_public'] and viewer.id not in item['_allowed_user_ids']:
            expected.append(None)
            continue
        prepared = item.copy()
        if item['room_id'] == private.id:
            prepared['title'] = (other if viewer == user else user).username
        if digest:
            count = sum(message.room_id == item['room_id'] and message.sender_id != viewer.id for message in messages)
            prepared.update(message_count=count, update_count=count, **{DIGEST_GROUP_ID: item['room_id']})
            expected.append(prepared if count else None)
        else:
            read_id = messages[viewer_index].pk
            prepared.update(message_count=1, is_read=item['object_id'] == read_id or (viewer == user and item['room_id'] == public.id))
            expected.append(prepared)
    provider = get_provider('room_messages')
    with django_assert_num_queries(1 if digest else 2):
        result = provider.prepare_digest_items(raw, viewer, since) if digest else provider.prepare_items(raw, viewer)
    assert result == expected
    assert raw == original


@pytest.mark.parametrize('digest', [False, True])
def test_chat_hooks_empty_batch_has_no_queries(user, django_assert_num_queries, digest):
    provider = get_provider('room_messages')
    since = timezone.now()
    with django_assert_num_queries(0):
        result = provider.prepare_digest_items([], user, since) if digest else provider.prepare_items([], user)
    assert result == []


def test_chat_digest_keeps_newest_own_source_but_counts_other_messages(chat_batch, monkeypatch):
    user, other, private, public, own, since, raw, messages = chat_batch
    original = deepcopy(raw)
    monkeypatch.setattr(feed, 'collect_feed_items', lambda cutoff: raw)
    result = feed.build_user_digest(user, since)
    assert {item['room_id'] for item in result} == {private.id, public.id}
    for item in result:
        source = next(source for source in original if source['object_id'] == item['object_id'])
        expected = {**source, 'message_count': 4, 'update_count': 5}
        if item['room_id'] == private.id:
            expected['title'] = other.username
        assert item == expected
        assert item['author'] == user
        assert item['timestamp'] == since + timedelta(minutes=5)
        assert item['object_id'] == messages[4 if item['room_id'] == private.id else 9].pk
    assert raw == original
