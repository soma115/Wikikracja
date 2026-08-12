"""
Project-wide utility functions
"""


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
    except (Exception):
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
