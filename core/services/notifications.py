"""Shared notification preference and unsubscribe services."""

from django.core import signing
from django.db import transaction
from django.utils import timezone

from core.utils import build_site_url
from obywatele.models import Uzytkownik

UNSUBSCRIBE_SALT = 'notifications.unsubscribe'
UNSUBSCRIBE_MAX_AGE = 60 * 60 * 24 * 365 * 5


def unsubscribe_user_notifications(user, *, source: str) -> None:
    """Disable all subscription notifications for a user, safely and idempotently."""
    profile = user.uzytkownik
    update_fields = [
        'email_frequency',
        'notifications_unsubscribed_at',
        'notifications_unsubscribe_source',
        'push_phone_enabled',
        'push_computer_enabled',
        'push_notifications_obywatele',
        'push_notifications_glosowania',
        'push_notifications_chat',
        'push_notifications_events',
        'push_notifications_post',
        'push_notifications_task',
        'push_notifications_survey',
    ]
    with transaction.atomic():
        profile.email_frequency = Uzytkownik.EmailFrequency.NEVER
        profile.notifications_unsubscribed_at = profile.notifications_unsubscribed_at or timezone.now()
        profile.notifications_unsubscribe_source = source
        profile.push_phone_enabled = False
        profile.push_computer_enabled = False
        for field in update_fields[5:]:
            setattr(profile, field, False)
        profile.save(update_fields=update_fields)


def notifications_unsubscribed(user) -> bool:
    try:
        return user.uzytkownik.notifications_unsubscribed_at is not None
    except (AttributeError, Uzytkownik.DoesNotExist):
        return False


def clear_notifications_unsubscribe(profile) -> None:
    if profile.notifications_unsubscribed_at is not None:
        profile.notifications_unsubscribed_at = None
        profile.notifications_unsubscribe_source = ''
        profile.save(update_fields=['notifications_unsubscribed_at', 'notifications_unsubscribe_source'])


def make_unsubscribe_token(user) -> str:
    return signing.dumps({'user_id': user.pk, 'purpose': 'all-notifications'}, salt=UNSUBSCRIBE_SALT)


def user_from_unsubscribe_token(token):
    from django.contrib.auth import get_user_model

    payload = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=UNSUBSCRIBE_MAX_AGE)
    if payload.get('purpose') != 'all-notifications':
        raise signing.BadSignature('Invalid unsubscribe purpose')
    return get_user_model().objects.get(pk=payload['user_id'])


def build_unsubscribe_url(user) -> str:
    return build_site_url(f'/email/unsubscribe/{make_unsubscribe_token(user)}/')


def unsubscribe_headers(user) -> dict[str, str]:
    url = build_unsubscribe_url(user)
    return {'List-Unsubscribe': f'<{url}>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}
