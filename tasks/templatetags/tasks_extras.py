from urllib.parse import urlencode

from django import template
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

register = template.Library()


@register.simple_tag(takes_context=True)
def tasks_stepper(context):
    """Build shared stepper context for the tasks module."""
    request = context.get('request')
    active = ''
    if request and getattr(request, 'resolver_match', None):
        active = request.resolver_match.url_name or ''

    current_tab = context.get('current_tab', '')
    current_sort = context.get('current_sort', request.GET.get('sort', 'date') if request else 'date')
    current_order = context.get('current_order', request.GET.get('order', 'desc') if request else 'desc')
    current_categories = context.get('current_categories') or []
    if request and not current_categories:
        current_categories = request.GET.getlist('category')

    def _url(viewname, tab=None, **kwargs):
        url = reverse(viewname, kwargs=kwargs)
        params = []
        if tab:
            params.append(('tab', tab))
        params.append(('sort', current_sort))
        params.append(('order', current_order))
        for c in current_categories:
            params.append(('category', c))
        return f"{url}?{urlencode(params)}"

    steps = [
        {'url': _url('tasks:list', tab='mine'), 'icon': 'user', 'label': _('Mine'), 'active': active == 'list' and current_tab == 'mine'},
        {'url': _url('tasks:list', tab='awaiting'), 'icon': 'hourglass-half', 'label': _('Awaiting'), 'active': active == 'list' and current_tab == 'awaiting'},
        {'url': _url('tasks:list', tab='active'), 'icon': 'spinner', 'label': _('In progress'), 'active': active == 'list' and current_tab == 'active'},
        {'url': _url('tasks:list', tab='finished'), 'icon': 'check', 'label': _('Finished'), 'active': active == 'list' and current_tab == 'finished'},
        {'url': _url('tasks:stats'), 'icon': 'chart-simple', 'label': _('Statistics'), 'active': active == 'stats'},
    ]

    cta_url = ''
    cta_label = ''
    if active == 'list' and current_tab in ('mine', 'awaiting', 'active', 'finished'):
        cta_url = reverse('tasks:add')
        cta_label = _('Add activity')

    return {
        'info_url': _url('tasks:help'),
        'info_title': _('How do activities work?'),
        'info_active': active == 'help',
        'steps': steps,
        'cta_url': cta_url,
        'cta_icon': 'plus',
        'cta_label': cta_label,
        'cta_title': cta_label,
    }
