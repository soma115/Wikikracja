from django import template
from django.utils.safestring import mark_safe

from core.richtext import plain_text, sanitize, sanitize_tinymce

register = template.Library()


@register.filter(name='richtext', is_safe=True)
def richtext(value):
    """
    Render user-entered text with allowed HTML (b/i/u/br/a), auto-linked URLs,
    and \\n converted to <br> (handled centrally by sanitize()). Output is marked safe.

    Replaces ad-hoc combinations of |linebreaks, |linebreaksbr, |urlize, |safe.
    """
    if not value:
        return ''
    return mark_safe(sanitize(str(value), linkify=True))


@register.filter(name='plain_text')
def plain_text_filter(value):
    """Convert rich text to plain text and decode HTML entities for snippets."""
    return plain_text(str(value)) if value else ''


@register.filter(name='tinymce_content', is_safe=True)
def tinymce_content(value):
    if not value:
        return ''
    return mark_safe(sanitize_tinymce(str(value)))
