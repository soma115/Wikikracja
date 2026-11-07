"""
Project-wide utility functions
"""

import hashlib

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

# Palette of muted accent colours that work on both light and dark backgrounds
_CITIZEN_COLORS = ['#0d6efd', '#6610f2', '#6f42c1', '#d63384', '#dc3545', '#fd7e14', '#198754', '#20c997', '#0dcaf0', '#0077b6', '#7b2d8b', '#c77dff']


def _citizen_color_index(username):
    return int(hashlib.md5(str(username).encode()).hexdigest(), 16) % len(_CITIZEN_COLORS)


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
    full_name = user.get_full_name()
    return full_name.title() if full_name else user.username


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


def default_toolbar_views():
    return [{'name': 'list', 'icon': 'list', 'title': _('List')}, {'name': 'grid', 'icon': 'grip', 'title': _('Grid')}]


def get_user_language(user):
    """Return a user's explicit language or the instance default."""
    try:
        language = user.uzytkownik.language
    except (AttributeError, ObjectDoesNotExist):
        language = ''
    return language or settings.LANGUAGE_CODE


def get_site_domain():
    """
    Get the current site's domain from the django_site table.
    Falls back to 'localhost' if Site is not configured.
    Returns:
        str: The domain of the current site (e.g., 'test.wikikracja.pl')
    """
    try:
        from django.contrib.sites.models import Site

        return Site.objects.get_current().domain
    except Site.DoesNotExist:
        return 'localhost'


def build_site_url(path: str) -> str:
    """
    Build a full absolute URL for the current site.
    Args:
        path (str): The path component (e.g., "/glosowania/details/1")
    Returns:
        str: Absolute URL including scheme and host.
    """
    from django.conf import settings

    scheme = getattr(settings, "SITE_PROTOCOL", "http")
    host = get_site_domain()
    return f"{scheme}://{host}{path}"


def build_detail_navigation(request, items, current_key, url_name, *, item_key=None, url_kwargs=None, query_string_for_item=None):
    """Build Previous/Next URLs for an ordered detail-page sequence."""
    items = list(items)
    item_key = item_key or (lambda item: item.pk)
    url_kwargs = url_kwargs or (lambda item: {"pk": item.pk})
    keys = [item_key(item) for item in items]

    try:
        current_index = keys.index(current_key)
    except ValueError:
        return {"previous_url": None, "next_url": None}

    query_string = request.GET.urlencode()
    query_string_for_item = query_string_for_item or (lambda item: query_string)

    def item_url(item):
        url = reverse(url_name, kwargs=url_kwargs(item))
        item_query_string = query_string_for_item(item)
        return f"{url}?{item_query_string}" if item_query_string else url

    return {"previous_url": item_url(items[current_index - 1]) if current_index > 0 else None, "next_url": item_url(items[current_index + 1]) if current_index < len(items) - 1 else None}
