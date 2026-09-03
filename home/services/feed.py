import logging
from datetime import timedelta as td
from datetime import timezone as dt_timezone

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from ..feed_registry import collect_feed_items, get_provider
from ..models import ReadStatus

log = logging.getLogger(__name__)

FEED_CACHE_KEY = "feed_raw_v2"
FEED_CACHE_TTL = 3600
FEED_DAYS = 90


def invalidate_feed_cache():
    try:
        cache.delete(FEED_CACHE_KEY)
    except Exception:
        log.warning("Could not invalidate feed cache; cache backend unavailable.", exc_info=True)


def build_read_status_map(user):
    return {
        content_type: set(object_ids)
        for content_type, object_ids in ((content_type, ReadStatus.objects.filter(user=user, content_type=content_type).values_list('object_id', flat=True)) for content_type in ReadStatus.ContentType.values)
    }


def generate_feed_raw():
    """
    Fetch all feed data WITHOUT user-specific is_read flags.
    Result is cached globally in Redis (TTL 1h). Each item stores
    content_type + object_id so is_read can be attached per-request.
    Invalidated by app-specific signals when feed-related models change.
    """
    cached = cache.get(FEED_CACHE_KEY)
    if cached is not None:
        return cached

    since = timezone.now() - td(days=FEED_DAYS)
    feed_items = collect_feed_items(since)

    events_items = [i for i in feed_items if i['content_type'] == 'event']
    other_items = [i for i in feed_items if i['content_type'] != 'event']
    events_items.sort(key=lambda x: x['timestamp'])
    other_items.sort(key=lambda x: x['timestamp'], reverse=True)
    feed_items = events_items + other_items

    cache.set(FEED_CACHE_KEY, feed_items, FEED_CACHE_TTL)
    return feed_items


def _chat_message_counts_since(user, room_ids, since):
    """Return {room_id: message_count} for the user since a given point.

    Counts messages in each room sent by someone else since `since`.
    Used by email digests where every new message matters, not just unread.
    """
    if not room_ids:
        return {}

    from chat.models import Message

    counts = Message.objects.filter(room_id__in=room_ids, time__gte=since).exclude(sender=user).values('room_id').annotate(msg_count=Count('id'))
    return {c['room_id']: c['msg_count'] for c in counts}


def generate_feed_items(user):
    """Generate unified chronological feed for a user, with is_read attached per-request."""
    raw_items = generate_feed_raw()
    read_status_map = build_read_status_map(user)

    ct_map = {
        'post': ReadStatus.ContentType.POST,
        'task': ReadStatus.ContentType.TASK,
        'event': ReadStatus.ContentType.EVENT,
        'decision': ReadStatus.ContentType.DECISION,
        'citizen': ReadStatus.ContentType.CITIZEN,
        'survey': ReadStatus.ContentType.SURVEY,
    }
    chat_message_ids = [item['object_id'] for item in raw_items if item['content_type'] == 'room_messages']
    from chat.models import MessageReadBy

    read_chat_message_ids = set(MessageReadBy.objects.filter(user=user, message_id__in=chat_message_ids).values_list('message_id', flat=True))
    seen_room_ids = set(user.seen_rooms.values_list('id', flat=True))

    feed_items = []
    for item in raw_items:
        ct = item['content_type']
        # rooms: filter to rooms the user has access to
        if ct == 'room_messages':
            if not item.get('_is_public') and user.id not in item.get('_allowed_user_ids', set()):
                continue
            if not item.get('_is_public'):
                other = next((name for uid, name in item.get('_allowed_usernames', {}).items() if uid != user.id), None)
                if other:
                    item = {**item, 'title': other}
            is_read = item['object_id'] in read_chat_message_ids or item['room_id'] in seen_room_ids
            item = {**item, 'is_read': is_read, 'message_count': 1}
        else:
            rs_ct = ct_map.get(ct)
            is_read = (item['object_id'] in read_status_map[rs_ct]) if rs_ct else False
            item = {**item, 'is_read': is_read}
        feed_items.append(item)

    return feed_items


def get_unread_count(user, items=None):
    """Return the number of unread feed items for a user."""
    if items is None:
        items = generate_feed_items(user)
    return sum(1 for item in items if not item['is_read'])


def _normalize_content_type(content_type: str) -> str:
    """Frontend sometimes uses the legacy alias 'message' for chat rooms."""
    return 'room_messages' if content_type == 'message' else content_type


def mark_feed_item_as_read(content_type: str, object_id: int, user) -> None:
    """Dispatch mark-as-read to the feed provider for the given content type."""
    content_type = _normalize_content_type(content_type)
    provider = get_provider(content_type)
    if provider is None or provider.mark_as_read is None:
        raise ValueError(f"Unsupported feed content type: {content_type}")
    provider.mark_as_read(object_id, user)


def mark_feed_item_as_unread(content_type: str, object_id: int, user) -> None:
    """Dispatch mark-as-unread to the feed provider for the given content type."""
    content_type = _normalize_content_type(content_type)
    provider = get_provider(content_type)
    if provider is None or provider.mark_as_unread is None:
        raise ValueError(f"Unsupported feed content type: {content_type}")
    provider.mark_as_unread(object_id, user)


def mark_all_feed_items_as_read(user) -> int:
    """Mark every unread feed item for the user as read and return the count."""
    feed_items = generate_feed_items(user)
    count = 0
    for item in feed_items:
        if not item['is_read']:
            content_type = _normalize_content_type(item['content_type'])
            provider = get_provider(content_type)
            if provider is None or provider.mark_as_read is None:
                continue
            provider.mark_as_read(item['object_id'], user)
            count += 1
    return count


def make_read_status_markers(content_type: str):
    """Return a generic (mark_as_read, mark_as_unread) pair backed by ReadStatus.

    Most feed providers only differ by their ``ReadStatus.ContentType`` constant,
    so this factory removes the duplicated marker functions in ``<app>/feed.py``.
    """
    from home.models import ReadStatus

    def mark_as_read(object_id: int, user) -> None:
        ReadStatus.objects.get_or_create(user=user, content_type=content_type, object_id=object_id)

    def mark_as_unread(object_id: int, user) -> None:
        ReadStatus.objects.filter(user=user, content_type=content_type, object_id=object_id).delete()

    return mark_as_read, mark_as_unread


def invalidate_feed_cache_on_change(sender, **kwargs) -> None:
    """Generic signal receiver that invalidates the global feed cache."""
    invalidate_feed_cache()


def _digest_group_key(item):
    """Return a grouping key for a feed item used in email digests.

    Citizen activities are grouped per user, room messages per room,
    and other content types per object.
    """
    ct = item['content_type']
    if ct == 'citizen':
        author = item.get('author')
        return (ct, author.id if author else item['object_id'])
    return (ct, item.get('room_id', item['object_id']))


def _sort_digest_items(items):
    """Sort digest items like the activity page: events ascending, rest descending."""
    epoch = timezone.datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
    events = [i for i in items if i['content_type'] == 'event']
    others = [i for i in items if i['content_type'] != 'event']
    events.sort(key=lambda x: x['timestamp'] or epoch)
    others.sort(key=lambda x: x['timestamp'] or epoch, reverse=True)
    return events + others


def build_user_digest(user, since):
    """Build a personalized list of activity items for an email digest.

    Aggregates multiple feed rows for the same user/room/object into one
    item and counts how many new messages appeared in chat rooms since
    `since`. Items are sorted with upcoming events first, then newest first.
    """
    raw_items = collect_feed_items(since)

    room_ids = [item['room_id'] for item in raw_items if item['content_type'] == 'room_messages']
    chat_counts = _chat_message_counts_since(user, room_ids, since)

    user_items = []
    for item in raw_items:
        ct = item['content_type']

        # Filter by the digest time window (events with future timestamps are kept).
        if item.get('timestamp') is not None and item['timestamp'] < since and ct != 'event':
            continue

        if ct == 'room_messages':
            if not item.get('_is_public') and user.id not in item.get('_allowed_user_ids', set()):
                continue
            if not item.get('_is_public'):
                other = next((name for uid, name in item.get('_allowed_usernames', {}).items() if uid != user.id), None)
                if other:
                    item = {**item, 'title': other}
            msg_count = chat_counts.get(item['room_id'], 0)
            if msg_count == 0:
                continue
            item = {**item, 'message_count': msg_count, 'update_count': msg_count}
        else:
            # ReadStatus tracking is irrelevant for email digests.
            item = {**item, 'update_count': 1}

        user_items.append(item)

    # Aggregate multiple activities for the same citizen/room/object.
    grouped = {}
    counts = {}
    for item in user_items:
        key = _digest_group_key(item)
        if key not in grouped or (item.get('timestamp') and (not grouped[key].get('timestamp') or item['timestamp'] > grouped[key]['timestamp'])):
            grouped[key] = item
        counts[key] = counts.get(key, 0) + 1

    aggregated = []
    for key, item in grouped.items():
        aggregated.append({**item, 'update_count': counts[key]})

    return _sort_digest_items(aggregated)
