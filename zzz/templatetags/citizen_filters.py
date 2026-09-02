import hashlib

from django import template

register = template.Library()


# Palette of muted accent colours that work on both light and dark backgrounds
_CITIZEN_COLORS = ['#0d6efd', '#6610f2', '#6f42c1', '#d63384', '#dc3545', '#fd7e14', '#198754', '#20c997', '#0dcaf0', '#0077b6', '#7b2d8b', '#c77dff']


@register.filter
def citizen_color(username):
    """Return a deterministic hex colour for a username."""
    idx = int(hashlib.md5(str(username).encode()).hexdigest(), 16) % len(_CITIZEN_COLORS)
    return _CITIZEN_COLORS[idx]


@register.filter
def citizen_color_class(username):
    """Return a deterministic CSS class for a username colour."""
    return 'citizen-color-' + str(int(hashlib.md5(str(username).encode()).hexdigest(), 16) % len(_CITIZEN_COLORS))
