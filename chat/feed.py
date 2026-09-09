from django.core.cache import cache
from django.utils import timezone

from core.feed_registry import DIGEST_GROUP_ID
from core.richtext import plain_text
from zzz.templatetags.citizen_filters import user_display_name

from .models import Message, MessageReadBy, Room
from .services import CHAT_UNREAD_CACHE_KEY, extract_mentions


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for non-archived chat rooms with recent messages."""
    # The guest Inbox is a contact channel, not part of the group's activity feed.
    all_rooms = Room.objects.filter(archived=False, is_inbox=False).prefetch_related('allowed', 'messages', 'messages__sender', 'messages__sender__uzytkownik')

    items = []
    for room in all_rooms:
        allowed_users = list(room.allowed.all())
        room_context = {
            'content_type': 'room_messages',
            'title': room.clean_title() if room.public else room.title,
            'url': f"/chat/#room_id={room.id}",
            'room_id': room.id,
            '_is_public': room.public,
            '_allowed_user_ids': {u.id for u in allowed_users},
            '_allowed_names': {u.id: user_display_name(u) for u in allowed_users},
        }
        messages = sorted((m for m in room.messages.all() if m.time >= since), key=lambda m: m.time, reverse=True)
        for msg in messages:
            # Skip system messages that have no explicit author and are not anonymous.
            if msg.sender is None and not msg.anonymous:
                continue
            items.append({**room_context, 'description': plain_text(msg.text), 'author': None if msg.anonymous else msg.sender, 'timestamp': msg.time, 'object_id': msg.id})
    return items


def _visible_item(item, user) -> dict | None:
    # rooms: filter to rooms the user has access to
    if not item.get('_is_public') and user.id not in item.get('_allowed_user_ids', set()):
        return None
    item = {**item}
    if not item.get('_is_public'):
        other = next((name for uid, name in item.get('_allowed_names', {}).items() if uid != user.id), None)
        if other:
            item['title'] = other
    return item


def prepare_items(items, user) -> list[dict | None]:
    if not items:
        return []

    message_ids = [item['object_id'] for item in items]
    read_message_ids = set(MessageReadBy.objects.filter(user=user, message_id__in=message_ids).values_list('message_id', flat=True))
    seen_room_ids = set(user.seen_rooms.values_list('id', flat=True))

    prepared_items = []
    for item in items:
        item = _visible_item(item, user)
        if item is not None:
            item['is_read'] = item['object_id'] in read_message_ids or item['room_id'] in seen_room_ids
            item['message_count'] = 1
        prepared_items.append(item)
    return prepared_items


def _chat_digest_stats(user, room_ids, since):
    """Return ({room_id: message_count}, {mentioned_room_id, ...}) since `since`.

    Uses a single query regardless of the number of rooms or messages. Counts
    messages sent by someone else and detects @mentions of `user` in one pass.
    """
    if not room_ids:
        return {}, set()

    counts = {}
    mentioned_rooms = set()
    messages = Message.objects.filter(room_id__in=room_ids, time__gte=since).exclude(sender=user).values('room_id', 'text')
    for msg in messages:
        room_id = msg['room_id']
        counts[room_id] = counts.get(room_id, 0) + 1
        if user.username in extract_mentions(msg['text']):
            mentioned_rooms.add(room_id)
    return counts, mentioned_rooms


def prepare_digest_items(items, user, since) -> list[dict | None]:
    if not items:
        return []

    room_ids = [item['room_id'] for item in items]
    chat_counts, mentioned_room_ids = _chat_digest_stats(user, room_ids, since)

    prepared_items = []
    for item in items:
        item = _visible_item(item, user)
        if item is not None:
            msg_count = chat_counts.get(item['room_id'], 0)
            if msg_count == 0:
                item = None
            else:
                item['message_count'] = msg_count
                item['update_count'] = msg_count
                item['is_mentioned'] = item['room_id'] in mentioned_room_ids
                item[DIGEST_GROUP_ID] = item['room_id']
        prepared_items.append(item)
    return prepared_items


def mark_as_read(object_id: int, user) -> None:
    try:
        message = Message.objects.get(pk=object_id)
        MessageReadBy.objects.get_or_create(message=message, user=user)
        message.room.seen_by.add(user)
        cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=user.id))
    except Message.DoesNotExist:
        pass


def mark_as_unread(object_id: int, user) -> None:
    try:
        message = Message.objects.get(pk=object_id)
        MessageReadBy.objects.filter(message=message, user=user).delete()
        message.room.seen_by.remove(user)
        cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=user.id))
    except Message.DoesNotExist:
        pass
