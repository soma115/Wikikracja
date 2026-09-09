from __future__ import annotations

from datetime import datetime, timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models import Q
from django.dispatch import receiver
from django.utils import timezone

PRESENCE_GROUP = 'presence'
PRESENCE_GREEN_MINUTES = 15
PRESENCE_YELLOW_DAYS = 7
PRESENCE_SOURCES = frozenset({'app', 'push'})


def record_presence(user, source: str, *, timestamp=None) -> bool:
    """Store a monotonic presence signal and return whether it changed."""
    if not getattr(user, 'is_authenticated', False) or source not in PRESENCE_SOURCES:
        return False

    timestamp = timestamp or timezone.now()
    profile = user.uzytkownik
    updated = type(profile).objects.filter(pk=profile.pk).filter(Q(last_presence_at__isnull=True) | Q(last_presence_at__lt=timestamp)).update(last_presence_at=timestamp, last_presence_source=source)
    if updated:
        profile.last_presence_at = timestamp
        profile.last_presence_source = source
    return bool(updated)


def get_presence_status(last_presence_at, now=None):
    """Return the public status and source for the latest presence signal."""
    if not last_presence_at:
        return 'red'
    if isinstance(last_presence_at, str):
        try:
            last_presence_at = datetime.fromisoformat(last_presence_at.replace('Z', '+00:00'))
        except ValueError:
            return 'red'
    if timezone.is_naive(last_presence_at):
        last_presence_at = timezone.make_aware(last_presence_at, timezone.get_current_timezone())

    now = now or timezone.now()
    age = now - last_presence_at
    if age <= timedelta(minutes=getattr(settings, 'PRESENCE_GREEN_MINUTES', PRESENCE_GREEN_MINUTES)):
        return 'green'
    if age <= timedelta(days=getattr(settings, 'PRESENCE_YELLOW_DAYS', PRESENCE_YELLOW_DAYS)):
        return 'yellow'
    return 'red'


def presence_data(user):
    profile = getattr(user, 'uzytkownik', None)
    timestamp = profile.last_presence_at if profile else None
    return {'presence_status': get_presence_status(timestamp), 'presence_source': profile.last_presence_source if profile else '', 'presence_timestamp': timestamp.isoformat() if timestamp else None}


def publish_presence(user, *, status=None):
    """Broadcast a compact presence update to every connected application tab."""
    profile = user.uzytkownik
    status = status or get_presence_status(profile.last_presence_at)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        PRESENCE_GROUP,
        {'type': 'presence.update', 'user_id': user.id, 'status': status, 'source': profile.last_presence_source, 'timestamp': profile.last_presence_at.isoformat() if profile.last_presence_at else None},
    )


@receiver(user_logged_in)
def record_login_presence(sender, request, user, **kwargs):
    if record_presence(user, 'app'):
        publish_presence(user)
