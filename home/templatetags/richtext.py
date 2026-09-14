from django import template
from django.utils.safestring import mark_safe

from core.richtext import sanitize, sanitize_tinymce

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


@register.filter(name='tinymce_content', is_safe=True)
def tinymce_content(value):
    if not value:
        return ''
    return mark_safe(sanitize_tinymce(str(value)))
