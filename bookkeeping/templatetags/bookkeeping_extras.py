from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def bookkeeping_active_tab(context):
    """Return the active bookkeeping tab based on the current URL name.

    URL names in this module follow the convention ``<entity>_<action>``,
    e.g. ``transaction_list`` or ``asset_update``. The empty index view is
    treated as the transactions tab.
    """
    request = context.get('request')
    if not request or not getattr(request, 'resolver_match', None):
        return ''
    url_name = request.resolver_match.url_name or ''
    if url_name == 'index':
        return 'transactions'
    for prefix, tab in (
        ('transaction', 'transactions'),
        ('partner', 'partners'),
        ('category', 'categories'),
        ('asset', 'assets'),
        ('report', 'reports'),
    ):
        if url_name.startswith(prefix):
            return tab
    return ''


@register.filter
def normalize_decimal(value):
    try:
        normalized = Decimal(value).normalize()
        return f"{normalized:f}"
    except (InvalidOperation, TypeError):
        return value


@register.filter
def get_item(dictionary, key):
    """
    Gets an item from a dictionary using the key.
    Usage: {{ dictionary|get_item:key }}
    """
    if not dictionary:
        return None
    return dictionary.get(key)
