from urllib.parse import urlencode

from django import template
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from glosowania.models import Decyzja
from glosowania.stepper import get_stepper_counts

register = template.Library()


@register.simple_tag(takes_context=True)
def glosowania_stepper(context, decision=None):
    """Build shared stepper context for the glosowania module."""
    request = context.get('request')
    active = ''
    if request and getattr(request, 'resolver_match', None):
        active = request.resolver_match.url_name or ''

    current_status = context.get('stepper_status') or getattr(decision, 'status', None)
    status_steps = {
        Decyzja.Status.PROPOSITION: 'proposition',
        Decyzja.Status.DISCUSSION: 'discussion',
        Decyzja.Status.REFERENDUM: 'referendum',
        Decyzja.Status.APPROVED: 'approved',
        Decyzja.Status.REJECTED: 'rejected',
    }
    active_step = status_steps.get(current_status, current_status if current_status in status_steps.values() else active if active in status_steps.values() else '')
    info_active = not current_status and context.get('stepper_info_active', active in ('parameters', 'parameters_propose', 'parameters_edit'))
    counts = get_stepper_counts()

    def _url(viewname, **kwargs):
        url = reverse(viewname, kwargs=kwargs)
        if request:
            params = {k: v for k, v in request.GET.items() if k in ('sort', 'order')}
            if params:
                url += '?' + urlencode(params)
        return url

    steps = [
        {'url': _url('glosowania:proposition'), 'icon': 'lightbulb', 'label': _('Suggestions'), 'count': counts['proposition'], 'active': active_step == 'proposition'},
        {'url': _url('glosowania:discussion'), 'icon': 'comments', 'label': _('Discussion'), 'count': counts['discussion'], 'active': active_step == 'discussion'},
        {'url': _url('glosowania:referendum'), 'icon': 'vote-yea', 'label': _('Referendum'), 'count': counts['referendum'], 'active': active_step == 'referendum'},
        {'url': _url('glosowania:approved'), 'icon': 'check', 'label': _('Approved'), 'count': counts['approved'], 'active': active_step == 'approved'},
        {'url': _url('glosowania:rejected'), 'icon': 'trash', 'label': '', 'count': counts['rejected'], 'active': active_step == 'rejected', 'is_rejected': True},
    ]

    cta_url = ''
    cta_label = ''
    if active in ('proposition', 'discussion', 'referendum', 'approved', 'rejected'):
        cta_url = reverse('glosowania:dodaj_nowy')
        cta_label = _('Add')

    return {
        'info_url': reverse('glosowania:parameters'),
        'info_title': _('How do votes work?'),
        'info_active': info_active,
        'steps': steps,
        'cta_url': cta_url,
        'cta_icon': 'plus',
        'cta_label': cta_label,
        'cta_title': cta_label,
    }
