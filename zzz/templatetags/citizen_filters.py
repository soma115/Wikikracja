import hashlib

from django import template

register = template.Library()


# Palette of muted accent colours that work on both light and dark backgrounds
_CITIZEN_COLORS = ['#0d6efd', '#6610f2', '#6f42c1', '#d63384', '#dc3545', '#fd7e14', '#198754', '#20c997', '#0dcaf0', '#0077b6', '#7b2d8b', '#c77dff']


def _citizen_color_index(username):
    return int(hashlib.md5(str(username).encode()).hexdigest(), 16) % len(_CITIZEN_COLORS)


@register.filter
def citizen_color_class(username):
    """Return a deterministic CSS class for a username colour."""
    return 'tw-citizen-color-' + str(_citizen_color_index(username))


def _as_user(user):
    """Accept a User or an Uzytkownik profile and return the User (or None)."""
    if user is None:
        return None
    return getattr(user, 'uid', user)


def user_display_name(user):
    """Full name when available, falling back to username. Accepts User or Uzytkownik."""
    user = _as_user(user)
    if not user:
        return ''
    return user.get_full_name() or user.username


def user_initials(user):
    """First letters of first and last name; falls back to the available part, then the username."""
    user = _as_user(user)
    if not user:
        return ''
    first = (user.first_name or '').strip()
    last = (user.last_name or '').strip()
    if first and last:
        return (first[0] + last[0]).upper()
    return (first or last or user.username or '')[:2].upper()


register.filter('user_initials', user_initials)
