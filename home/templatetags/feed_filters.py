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
        'post': _('Dokumenty'),
        'task': _('Task'),
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
