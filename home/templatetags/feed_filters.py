import hashlib

from django import template
from django.utils.translation import gettext_lazy as _

register = template.Library()


@register.filter
def content_type_color(content_type):
    """Return Bootstrap color class for content type (kept in sync with the
    category colors used on the search page, see home/templates/home/search.html)"""
    color_map = {
        'post': 'primary',
        'task': 'warning',
        'event': 'success',
        'message': 'info',
        'room_messages': 'info',  # New content type for grouped room messages
        'decision': 'danger',
        'citizen': 'secondary',
        'membership': 'secondary',
        'transaction': 'primary',
    }
    return color_map.get(content_type, 'secondary')


@register.filter
def content_type_label(content_type):
    """Return translated label for content type"""
    label_map = {
        'post': _('Post'),
        'task': _('Task'),
        'event': _('Event'),
        'message': _('Message'),
        'room_messages': _('Chat room'),  # New content type for grouped room messages
        'decision': _('Decision'),
        'citizen': _('Citizen'),
        'membership': _('Membership'),
        'transaction': _('Transaction'),
    }
    return label_map.get(content_type, content_type.title())


# Palette of muted accent colours that work on both light and dark backgrounds
_CITIZEN_COLORS = [
    '#0d6efd',
    '#6610f2',
    '#6f42c1',
    '#d63384',
    '#dc3545',
    '#fd7e14',
    '#198754',
    '#20c997',
    '#0dcaf0',
    '#0077b6',
    '#7b2d8b',
    '#c77dff',
]


@register.filter
def citizen_color(username):
    """Return a deterministic hex colour for a username."""
    idx = int(hashlib.md5(str(username).encode()).hexdigest(), 16) % len(_CITIZEN_COLORS)
    return _CITIZEN_COLORS[idx]
