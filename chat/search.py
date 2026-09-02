from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from home.colors import category_color

from .models import Message, Room


def search(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return search results for chat rooms and messages visible to the user."""
    if 'chat' not in active_cats:
        return []

    results = []
    accessible_rooms = Room.objects.filter(allowed=user)

    rooms = accessible_rooms.filter(title__icontains=query).distinct()[:limit]
    for obj in rooms:
        results.append({'cat': 'chat', 'type': _('Chat'), 'type_color': category_color('chat'), 'title': obj.displayed_name(user), 'description': '', 'url': f'/chat/#room_id={obj.pk}'})

    messages_qs = Message.objects.filter(Q(text__icontains=query), room__in=accessible_rooms).select_related('sender', 'room').order_by('-time').distinct()[: limit + 5]

    for obj in messages_qs:
        sender_name = str(_('System')) if obj.sender is None else (str(_('Anonymous')) if obj.anonymous else obj.sender.username)
        results.append(
            {
                'cat': 'chat',
                'type': _('Chat message'),
                'type_color': category_color('chat'),
                'title': obj.room.displayed_name(user),
                'description': f'{sender_name}: {strip_tags(obj.text)[:100]}',
                'url': f'/chat/#room_id={obj.room.pk}',
            }
        )

    return results
