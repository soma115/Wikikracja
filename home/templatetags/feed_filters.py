import hashlib

from django import template
from django.utils.translation import gettext_lazy as _

from home.colors import category_color

register = template.Library()


@register.filter
def content_type_color(content_type):
    """Return Bootstrap color class for content type. Backed by the single
    source of truth in home/colors.py (CATEGORY_COLORS), also used by
    home.views.global_search and home/templates/home/search.html."""
    return category_color(content_type)


@register.filter
def content_type_label(content_type):
    """Return translated label for content type"""
    label_map = {
        'post': _('Post'),
        'task': _('Task'),
        'event': _('Event'),
        'message': _('Message'),
        'room_messages': _('Chat'),  # New content type for grouped room messages
        'decision': _('Decision'),
        'citizen': _('Citizen'),
        'membership': _('Membership'),
        'transaction': _('Transaction'),
        'survey': _('Survey'),
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
