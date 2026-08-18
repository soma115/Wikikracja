import logging
from datetime import timedelta as td

from django.core.cache import cache
from django.db.models import Count, Exists, OuterRef
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..feed_registry import collect_feed_items, get_provider
from ..models import ReadStatus

log = logging.getLogger(__name__)

FEED_CACHE_KEY = "feed_raw_v1"
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


def _unread_chat_message_counts(user, room_ids):
    """Return {room_id: unread_count} for the user.

    Counts messages in each room that the user has not marked as read
    (via MessageReadBy) and that were sent by someone else.  Messages
    older than the feed window are ignored, matching the raw feed cutoff.
    """
    if not room_ids:
        return {}

    # Local import to keep this module importable without chat loaded.
    from chat.models import Message, MessageReadBy

    since = timezone.now() - td(days=FEED_DAYS)
    read = MessageReadBy.objects.filter(user=user, message_id=OuterRef('id'))

    counts = Message.objects.filter(room_id__in=room_ids, time__gte=since).exclude(sender=user).filter(~Exists(read)).values('room_id').annotate(unread=Count('id'))
    return {c['room_id']: c['unread'] for c in counts}


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
    seen_room_ids = set(user.seen_rooms.values_list('id', flat=True))
    room_ids = [item['object_id'] for item in raw_items if item['content_type'] == 'room_messages']
    unread_chat_counts = _unread_chat_message_counts(user, room_ids)

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
                    item = {**item, 'title': _("Messages in %(room_title)s") % {'room_title': other}}
            is_read = item['object_id'] in seen_room_ids
            item = {**item, 'is_read': is_read, 'message_count': unread_chat_counts.get(item['object_id'], 0)}
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
