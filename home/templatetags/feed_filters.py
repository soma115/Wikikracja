from django import template
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from core.colors import category_color

register = template.Library()


@register.filter
def display_name(user):
    """Return the user's full name when available, falling back to username."""
    if not user:
        return ''
    if hasattr(user, 'uid'):
        user = user.uid
    return user.get_full_name() or user.username


@register.filter
def content_type_color(content_type):
    """Return the semantic color name for a content type. Backed by the
    single source of truth in core/colors.py (CATEGORY_COLORS), also used by
    home.views.global_search and home/templates/home/search.html."""
    return category_color(content_type)


@register.filter
def content_type_label(content_type):
    """Return translated label for content type"""
    label_map = {
        'post': _('Dokumenty'),
        'task': pgettext_lazy('task', 'Activity'),
        'event': _('Kalendarz'),
        'message': _('Message'),
        'room_messages': _('Chat'),  # New content type for grouped room messages
        'decision': _('Głosowania'),
        'citizen': _('Citizen'),
        'membership': _('Membership'),
        'transaction': _('Transaction'),
        'survey': _('Ankiety'),
    }
    return label_map.get(content_type, content_type.title())
