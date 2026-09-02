import logging

from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import gettext as _

import zzz
from board.models import Post

log = logging.getLogger(__name__)


def footer(request: HttpRequest):
    footer = Post.get_system_post('footer')
    return {'footer': footer}


def site_name(request):
    from site_settings.params import get_param

    site = getattr(request, 'site', None)
    return {'site_name': get_param('site_name') or getattr(site, 'name', '') or settings.SITE_NAME, 'app_version': zzz.__version__}


def group_is_public(request):
    from site_settings.params import get_param

    return {'group_is_public': get_param('group_is_public')}


def unread_count(request):
    if not request.user.is_authenticated:
        return {'unread_count': 0}
    cached = getattr(request, '_unread_count', None)
    if cached is not None:
        return {'unread_count': cached}
    from home.services.feed import get_unread_count

    return {'unread_count': get_unread_count(request.user)}


def upload_limits(request):
    return {
        'UPLOAD_IMAGE_MAX_SIZE_MB': settings.UPLOAD_IMAGE_MAX_SIZE_MB,
        'UPLOAD_ATTACHMENT_MAX_SIZE_MB': settings.UPLOAD_ATTACHMENT_MAX_SIZE_MB,
        'UPLOAD_IMAGE_MAX_SIZE_MESSAGE': _("Image is too large (max %s MB)."),
        'UPLOAD_ATTACHMENT_MAX_SIZE_MESSAGE': _("File is too large (max %s MB)."),
    }
