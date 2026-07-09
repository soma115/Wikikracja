import logging

from django.conf import settings
from django.http import HttpRequest

import zzz
from board.models import Post

log = logging.getLogger(__name__)


def footer(request: HttpRequest):
    footer = Post.get_system_post('footer')
    return {
        'footer': footer
    }


def site_description(request):
    from site_settings.params import get_param
    site = getattr(request, 'site', None)
    return {
        'site_name': get_param('site_name') or getattr(site, 'name', '') or settings.SITE_NAME,
        'site_description': get_param('site_description') or settings.SITE_DESCRIPTION,
        'app_version': zzz.__version__,
    }


def group_is_public(request):
    from site_settings.params import get_param
    return {
        'group_is_public': get_param('group_is_public'),
    }
