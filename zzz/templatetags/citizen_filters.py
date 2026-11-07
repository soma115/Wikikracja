from django import template
from django.utils.translation import gettext as _

from core.presence import get_presence_status
from core.utils import citizen_color_class, user_display_name, user_initials

register = template.Library()

register.filter('citizen_color_class', citizen_color_class)
register.filter('user_display_name', user_display_name)
register.filter('user_initials', user_initials)


@register.filter
def presence_status(timestamp):
    return get_presence_status(timestamp)


@register.filter
def presence_status_label(status):
    return {'green': _('Active now'), 'yellow': _('Active recently'), 'red': _('No recent activity')}.get(status, _('No recent activity'))


@register.filter
def presence_source_label(source):
    return {'app': _('Application activity'), 'push': _('Push notification received')}.get(source, _('No recent activity'))
