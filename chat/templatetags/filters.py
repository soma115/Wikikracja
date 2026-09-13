from django import template
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from chat.models import Message

register = template.Library()


@register.filter('relative_chat_date')
def relative_chat_date(value):
    """Relative date for room list: HH:MM (today), 'Yesterday', day name (<7d), '20 kwi' (same year), '20 kwi 2024' (older)."""
    if value is None:
        return ''
    now = timezone.localtime(timezone.now())
    value = timezone.localtime(value)
    delta_days = (now.date() - value.date()).days
    if delta_days == 0:
        return date_format(value, 'H:i')
    if delta_days == 1:
        return _('Yesterday')
    if delta_days < 7:
        return date_format(value, 'l').capitalize()
    if value.year == now.year:
        return date_format(value, 'j M')
    return date_format(value, 'j M Y')


@register.filter('name_for')
def name_for(room, user):
    """Returns name of room given user will see"""
    return room.displayed_name(user)


@register.filter('other_user')
def other_user(room, user):
    """Returns the other user in a private 1-to-1 room (None for public rooms)."""
    if room.public:
        return None
    return room.get_other(user)


def _is_seen(room, user):
    """Return True when the user has read every message from other users."""
    if hasattr(room, 'is_seen') and hasattr(room, 'messages_count'):
        return room.is_seen or room.messages_count == 0
    return not Message.objects.filter(room_id=room.pk).exclude(room__seen_by=user).exclude(sender_id=user.id).exclude(read_by__user_id=user.id).exists()


@register.filter('is_seen_by')
def is_seen_by(room, user):
    """Returns 'true'/'false' string for JS data-seen attribute."""
    return "true" if _is_seen(room, user) else "false"


@register.filter('seen_by')
def seen_by(room, user):
    """Returns CSS class string: '' if seen, 'tw-room-link--not-seen' if unseen."""
    return "" if _is_seen(room, user) else "tw-room-link--not-seen"


@register.filter('is_muted_by')
def is_muted_by(room, user):
    """Returns True if the room is muted by the user"""
    # Use prefetched data if available
    if hasattr(room, '_prefetched_objects_cache') and 'muted_by' in room._prefetched_objects_cache:
        return any(u.id == user.id for u in room.muted_by.all())
    return room.muted_by.filter(id=user.id).exists()
