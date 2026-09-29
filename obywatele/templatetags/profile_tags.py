import html
from urllib.parse import urlencode

from django import template
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from obywatele.models import ResourceAssignment

register = template.Library()


@register.filter
def plain_text(value):
    """Strip HTML tags and decode HTML entities."""
    return html.unescape(strip_tags(value or ''))


@register.filter
def getattribute(obj, attr):
    """
    Gets an attribute of an object dynamically from a string name.

    Usage: {{ profile|getattribute:field_name }}
    """
    return getattr(obj, attr, None)


@register.inclusion_tag('obywatele/includes/notification_row.html')
def notification_row(notification_type, title, description, is_enabled):
    """
    Renders a notification settings row.

    Args:
        notification_type: Type identifier (e.g., 'obywatele', 'glosowania', 'chat')
        title: Display title for the notification type
        description: Description text for the notification
        is_enabled: Boolean indicating if notification is currently enabled
    """
    return {'notification_type': notification_type, 'title': title, 'description': description, 'is_enabled': is_enabled}


@register.simple_tag(takes_context=True)
def obywatele_stepper(context):
    """Build shared stepper context for the obywatele module."""
    request = context.get('request')
    active = ''
    if request and getattr(request, 'resolver_match', None):
        active = request.resolver_match.url_name or ''

    def _url(viewname, **kwargs):
        url = reverse(viewname, kwargs=kwargs)
        if request:
            params = {k: v for k, v in request.GET.items() if k in ('sort', 'aktywnosc')}
            if params:
                url += '?' + urlencode(params)
        return url

    counts = User.objects.aggregate(citizens=Count('id', filter=Q(is_active=True)), candidates=Count('id', filter=Q(is_active=False, uzytkownik__isnull=False)))
    resource_count = ResourceAssignment.objects.filter(profile__uid__is_active=True).count()
    steps = [
        {'url': _url('obywatele:obywatele'), 'icon': 'users', 'label': _('Citizens'), 'count': counts['citizens'], 'active': active in ('obywatele', 'obywatele_szczegoly')},
        {'url': _url('obywatele:poczekalnia'), 'icon': 'user-clock', 'label': _('Candidates'), 'count': counts['candidates'], 'active': active in ('poczekalnia', 'poczekalnia_szczegoly')},
        {'url': _url('obywatele:assets'), 'icon': 'boxes-stacked', 'label': _('Resources'), 'count': resource_count, 'active': active == 'assets'},
    ]

    cta_url = ''
    cta_label = ''
    if active != 'zaproponuj_osobe':
        cta_url = reverse('obywatele:zaproponuj_osobe')
        cta_label = _('Invite')

    return {
        'info_url': reverse('obywatele:parameters'),
        'info_title': _('Parameters'),
        'info_active': active == 'parameters',
        'steps': steps,
        'cta_url': cta_url,
        'cta_icon': 'plus',
        'cta_label': cta_label,
        'cta_title': cta_label,
    }
