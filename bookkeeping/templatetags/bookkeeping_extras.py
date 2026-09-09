from decimal import Decimal, InvalidOperation

from django import template
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

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
    for prefix, tab in (('transaction', 'transactions'), ('partner', 'partners'), ('category', 'categories'), ('asset', 'assets'), ('report', 'reports')):
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


@register.simple_tag(takes_context=True)
def bookkeeping_stepper(context):
    """Build shared stepper context for the bookkeeping module."""
    request = context.get('request')
    active = ''
    if request and getattr(request, 'resolver_match', None):
        active = request.resolver_match.url_name or ''
    if active == 'index':
        active = 'transaction_list'

    tab = ''
    for prefix, name in (('transaction', 'transactions'), ('partner', 'partners'), ('category', 'categories'), ('asset', 'assets'), ('report', 'reports')):
        if active.startswith(prefix):
            tab = name
            break

    steps = [
        {'url': reverse('bookkeeping:transaction_list'), 'icon': 'money-bill-transfer', 'label': _('Transactions'), 'active': tab == 'transactions'},
        {'url': reverse('bookkeeping:partner_list'), 'icon': 'handshake', 'label': _('Partners'), 'active': tab == 'partners'},
        {'url': reverse('bookkeeping:category_list'), 'icon': 'tags', 'label': _('Categories'), 'active': tab == 'categories'},
        {'url': reverse('bookkeeping:asset_list'), 'icon': 'coins', 'label': _('Assets'), 'active': tab == 'assets'},
        {'url': reverse('bookkeeping:report_list'), 'icon': 'chart-pie', 'label': _('Reports'), 'active': tab == 'reports'},
    ]

    cta_map = {
        'transactions': ('bookkeeping:transaction_create', _('Add transaction')),
        'partners': ('bookkeeping:partner_create', _('Add partner')),
        'categories': ('bookkeeping:category_create', _('Add category')),
        'assets': ('bookkeeping:asset_create', _('Add asset')),
    }
    cta_url = ''
    cta_label = ''
    if active.endswith('_list') and tab in cta_map:
        viewname, cta_label = cta_map[tab]
        cta_url = reverse(viewname)

    return {'steps': steps, 'cta_url': cta_url, 'cta_icon': 'plus', 'cta_label': cta_label, 'cta_title': cta_label}
