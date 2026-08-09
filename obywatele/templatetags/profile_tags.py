import html

from django import template
from django.utils.html import strip_tags

register = template.Library()


@register.filter
def plain_text(value):
    """Strip HTML tags and decode HTML entities."""
    return html.unescape(strip_tags(value or ''))


@register.filter
def getattribute(obj, attr):
    """
    Gets an attribute of an object dynamically from a string name.

    Usage: {{ profile|getattribute:field_name }}
    """
    return getattr(obj, attr, None)


@register.inclusion_tag('obywatele/includes/notification_row.html')
def notification_row(notification_type, title, description, is_enabled):
    """
    Renders a notification settings row.

    Args:
        notification_type: Type identifier (e.g., 'obywatele', 'glosowania', 'chat')
        title: Display title for the notification type
        description: Description text for the notification
        is_enabled: Boolean indicating if notification is currently enabled
    """
    return {'notification_type': notification_type, 'title': title, 'description': description, 'is_enabled': is_enabled}
