from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Message, MessageReadBy, Room
from .services import CHAT_UNREAD_CACHE_KEY


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for non-archived chat rooms with recent messages."""
    # The guest Inbox is a contact channel, not part of the group's activity feed.
    all_rooms = Room.objects.filter(archived=False, is_inbox=False).prefetch_related('allowed', 'messages', 'messages__sender', 'messages__sender__uzytkownik')

    items = []
    for room in all_rooms:
        allowed_users = list(room.allowed.all())
        room_context = {
            'content_type': 'room_messages',
            'title': room.title,
            'url': f"/chat/#room_id={room.id}",
            'room_id': room.id,
            '_is_public': room.public,
            '_allowed_user_ids': {u.id for u in allowed_users},
            '_allowed_usernames': {u.id: u.username for u in allowed_users},
        }
        messages = sorted((m for m in room.messages.all() if m.time >= since), key=lambda m: m.time, reverse=True)
        for msg in messages:
            # Skip system messages that have no explicit author and are not anonymous.
            if msg.sender is None and not msg.anonymous:
                continue
            items.append({**room_context, 'description': strip_tags(msg.text), 'author': msg.sender, 'timestamp': msg.time, 'object_id': msg.id})
    return items


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
