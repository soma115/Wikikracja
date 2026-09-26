"""
Project-wide utility functions
"""

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse


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
