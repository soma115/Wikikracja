import logging
import threading

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from firebase_admin import messaging
from push_notifications.models import GCMDevice

from zzz.utils import get_site_domain

log = logging.getLogger(__name__)
domain = get_site_domain()


def _icon_url():
    return f"https://{domain}/favicon.ico"


def build_notification(title, body, click_action, tag, icon=None, **extra):
    """Build a notification payload shared by FCM and WebSocket dispatchers."""
    return {
        'title': title,
        'body': body,
        'icon': icon or _icon_url(),
        'click_action': click_action,
        'tag': tag,
        **extra,
    }


def _build_fcm_message(notification):
    """Build a Firebase `messaging.Message` from a generic notification payload."""
    data = {k: str(v) for k, v in notification.items()}
    return messaging.Message(
        notification=messaging.Notification(title=notification['title'], body=notification['body']),
        data=data,
        webpush=messaging.WebpushConfig(
            headers={'Urgency': 'high'},
            notification=messaging.WebpushNotification(
                title=notification['title'],
                body=notification['body'],
                icon=notification['icon'],
                badge=notification['icon'],
                tag=notification['tag'],
                require_interaction=True,
                data={k: str(v) for k, v in notification.items() if k in (
                    'click_action', 'room_id', 'room_name', 'event_id', 'vote_id', 'citizen_id'
                )},
            ),
            fcm_options=messaging.WebpushFCMOptions(link=notification['click_action']),
        )
    )


def _fcm_ready():
    try:
        import firebase_admin
        return bool(firebase_admin._apps)
    except Exception:
        return False


_gcm_migrated = False


def _migrate_legacy_gcm_devices():
    """One-time conversion of legacy GCM device rows to FCM (GCM is no longer supported).

    New devices are always registered as FCM (see chat/push_api.py), so this only matters
    for rows created before that migration. Memoized per-process to avoid running this
    UPDATE on every single notification send.
    """
    global _gcm_migrated
    if _gcm_migrated:
        return
    GCMDevice.objects.filter(cloud_message_type='GCM').update(cloud_message_type='FCM')
    _gcm_migrated = True


# Maps a notification category to the Uzytkownik push preference field.
_PUSH_FIELDS = {
    'obywatele': 'push_notifications_obywatele',
    'glosowania': 'push_notifications_glosowania',
    'chat': 'push_notifications_chat',
    'events': 'push_notifications_events',
}


def _push_enabled_for_user(user, notification_type):
    """Return True if the user has not disabled push for the given category."""
    if not notification_type:
        return True
    field = _PUSH_FIELDS.get(notification_type)
    if not field:
        return True
    try:
        return getattr(user.uzytkownik, field, True)
    except Exception:
        return True


def _push_user_ids(notification_type):
    """Return active user IDs that have push enabled for the given category."""
    if not notification_type:
        return None
    field = _PUSH_FIELDS.get(notification_type)
    if not field:
        return None
    User = get_user_model()
    return set(User.objects.filter(
        is_active=True,
        **{f'uzytkownik__{field}': True}
    ).values_list('id', flat=True))


def send_fcm_to_user_sync(user, notification, notification_type=None):
    """Send an FCM push notification to a single user's active devices."""
    if not _fcm_ready():
        log.warning(f"FCM skipped for user {user.id}: Firebase not initialized")
        return 0

    if not _push_enabled_for_user(user, notification_type):
        log.debug(f"Push disabled for user {user.id} ({notification_type})")
        return 0

    _migrate_legacy_gcm_devices()
    fcm_devices = GCMDevice.objects.filter(user=user, active=True, cloud_message_type='FCM')
    if not fcm_devices.exists():
        log.debug(f"No FCM devices for user {user.id}")
        return 0

    try:
        message = _build_fcm_message(notification)
        result = fcm_devices.send_message(message)
        if result and result.success_count > 0:
            log.info(f"FCM sent {result.success_count} notification(s) to user {user.id}")
        if result:
            for idx, resp in enumerate(result.responses):
                if not resp.success:
                    log.warning(f"FCM response {idx} failed for user {user.id}: {resp.exception}")
        return result.success_count if result else 0
    except Exception as e:
        log.error(f"FCM failed for user {user.id}: {e}", exc_info=True)
    return 0


def send_fcm_to_all_sync(notification, user_ids=None, notification_type=None):
    """Broadcast an FCM push notification to all active users or a subset of user IDs."""
    if not _fcm_ready():
        log.warning("FCM skipped: Firebase not initialized")
        return 0

    if user_ids is None and notification_type:
        user_ids = _push_user_ids(notification_type)

    _migrate_legacy_gcm_devices()
    qs = GCMDevice.objects.filter(user__is_active=True, active=True, cloud_message_type='FCM')
    if user_ids is not None:
        qs = qs.filter(user_id__in=user_ids)
    if not qs.exists():
        log.debug("No active FCM devices found")
        return 0

    try:
        message = _build_fcm_message(notification)
        result = qs.send_message(message)
        if result and result.success_count > 0:
            log.info(f"FCM sent {result.success_count} notification(s)")
        if result:
            for idx, resp in enumerate(result.responses):
                if not resp.success:
                    log.warning(f"FCM response {idx} failed: {resp.exception}")
        return result.success_count if result else 0
    except Exception as e:
        log.error(f"FCM broadcast failed: {e}", exc_info=True)
    return 0


def send_websocket_to_user_sync(user_id, notification, ws_type='notification'):
    """Send a WebSocket notification to a single user's personal group."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        log.warning("Channel layer not configured; skipping WebSocket notification")
        return

    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {"type": ws_type, "notification": notification}
        )
    except Exception as e:
        log.warning(f"WebSocket notification failed for user {user_id}: {e}")


def send_websocket_to_all_sync(notification, ws_type='notification', notification_type=None, user_ids=None):
    """Broadcast a WebSocket notification to all active users' personal groups.

    Pass `user_ids` to reuse an already-computed set (e.g. from `send_notification_to_all_sync`)
    and skip a redundant preference lookup query.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        log.warning("Channel layer not configured; skipping WebSocket broadcast")
        return

    if user_ids is None:
        user_ids = _push_user_ids(notification_type)

    User = get_user_model()
    queryset = User.objects.filter(is_active=True)
    if user_ids is not None:
        queryset = queryset.filter(id__in=user_ids)
    for user_id in queryset.values_list('id', flat=True):
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {"type": ws_type, "notification": notification}
            )
        except Exception as e:
            log.warning(f"WebSocket broadcast failed for user {user_id}: {e}")


def send_notification_to_all_sync(notification, ws_type='notification', notification_type=None):
    """Send both FCM and WebSocket notifications to all active users."""
    user_ids = _push_user_ids(notification_type)
    send_fcm_to_all_sync(notification, user_ids=user_ids)
    send_websocket_to_all_sync(notification, ws_type, user_ids=user_ids)


def send_notification_to_all_in_thread(notification, ws_type='notification', notification_type=None, daemon=True):
    """Send both FCM and WebSocket notifications to all active users in a background thread.

    Use this from request-handling code paths (views, forms) so the HTTP response doesn't
    block on the WebSocket broadcast loop (one channel-layer round trip per active user).
    Mirrors the pattern used by `send_bulk_email_in_thread` for emails. Management commands
    that already run out-of-band can keep using `send_notification_to_all_sync` directly.
    """
    t = threading.Thread(
        target=send_notification_to_all_sync,
        args=(notification,),
        kwargs={'ws_type': ws_type, 'notification_type': notification_type},
        daemon=daemon,
    )
    t.start()
    return t
