from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from .models import Room
from .services import CHAT_UNREAD_CACHE_KEY


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for non-archived chat rooms with recent messages."""
    all_rooms = Room.objects.filter(archived=False).prefetch_related('allowed', 'messages', 'messages__sender', 'messages__sender__uzytkownik')

    items = []
    for room in all_rooms:
        recent_msgs = sorted([m for m in room.messages.all() if m.time >= since], key=lambda m: m.time, reverse=True)[:5]
        if recent_msgs:
            latest_message = recent_msgs[0]
            message_list = []
            for msg in reversed(recent_msgs):
                clean_text = strip_tags(msg.text)
                author_name = msg.sender.username if msg.sender else 'System'
                message_list.append(f"- <strong>{author_name}:</strong> {clean_text}")
            allowed_users = list(room.allowed.all())
            items.append(
                {
                    'content_type': 'room_messages',
                    'title': _("Messages in %(room_title)s") % {'room_title': room.title},
                    'description': '\n'.join(message_list),
                    'author': latest_message.sender,
                    'timestamp': latest_message.time,
                    'url': f"/chat/#room_id={room.id}",
                    'object_id': room.id,
                    'room_id': room.id,
                    'message_count': len(recent_msgs),
                    '_is_public': room.public,
                    '_allowed_user_ids': {u.id for u in allowed_users},
                    '_allowed_usernames': {u.id: u.username for u in allowed_users},
                }
            )
    return items


def mark_as_read(object_id: int, user) -> None:
    try:
        room = Room.objects.get(id=object_id)
        room.seen_by.add(user)
        cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=user.id))
    except Room.DoesNotExist:
        pass


def mark_as_unread(object_id: int, user) -> None:
    try:
        room = Room.objects.get(id=object_id)
        room.seen_by.remove(user)
        cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=user.id))
    except Room.DoesNotExist:
        pass
