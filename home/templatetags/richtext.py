from django import template
from django.utils.safestring import mark_safe

from core.richtext import sanitize

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
