import html
import logging
import os
import re
import threading
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.db.utils import DatabaseError
from django.dispatch import receiver
from django.utils import formats
from django.utils.translation import gettext as _
from django.utils.translation import override
from firebase_admin import messaging
from push_notifications.models import GCMDevice

from core.richtext import strip_tags
from core.services.notifications import notifications_unsubscribed, unsubscribe_headers
from core.signals import (
    citizen_accepted,
    citizen_blocked,
    citizen_proposed,
    document_created,
    event_created,
    event_starting,
    event_updated,
    important_post_published,
    survey_created,
    survey_updated,
    task_created,
    task_helper_joined,
    task_status_changed,
    transaction_created,
    transaction_updated,
    vote_argument_added,
    vote_started,
    vote_state_changed,
)
from core.utils import build_site_url, get_site_domain, get_user_language
from site_settings.models import SiteParameters
from site_settings.services import get_branding_version

log = logging.getLogger(__name__)

# Prefix for every log line in the notification build/send/receive pipeline so the
# whole journey of a notification can be found with a single search — in server logs
# and in the browser console (see chat/static/chat/js/*.js, which use the same tag) —
# regardless of which of the many code paths (FCM, WebSocket, chat, events, votes,
# citizens...) it went through.
NOTIF_LOG_TAG = "[NOTIFDBG]"


def _icon_url():
    ss = SiteParameters.get()
    derived_favicon = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived', 'favicon.ico')
    if ss.brand_mark and os.path.isfile(derived_favicon):
        version = get_branding_version(ss)
        return build_site_url(f'/media/site_branding/derived/favicon.ico?v={version}')
    return build_site_url('/static/home/images/favicon.ico')


def build_notification(title, body, click_action, tag, icon=None, **extra):
    """Build a notification payload shared by FCM and WebSocket dispatchers.

    Every notification gets a unique `notification_id` so its journey (built ->
    sent via FCM/WebSocket -> shown/clicked/skipped/errored on the client) can be
    traced end-to-end by grepping logs for that ID. See chat/push_api.py's
    PushNotificationAckView for the client-side "it was actually shown" half.
    """
    notification_id = uuid.uuid4().hex
    notification = {'notification_id': notification_id, 'title': title, 'body': body, 'icon': icon or _icon_url(), 'click_action': click_action, 'tag': tag, **extra}
    log.debug(f"{NOTIF_LOG_TAG} Built notification {notification_id}: tag={tag} title={title!r}")
    return notification


def _fcm_https_url(url):
    """Return an absolute HTTPS URL accepted by Firebase Webpush."""
    if url.startswith('/'):
        url = build_site_url(url)
    parsed = urlsplit(url)
    if not parsed.netloc or parsed.scheme not in ('http', 'https'):
        raise ValueError('FCM click_action must be an absolute HTTP(S) URL')
    return urlunsplit(parsed._replace(scheme='https'))


def _build_fcm_message(notification):
    """Build a Firebase `messaging.Message` from a generic notification payload."""
    fcm_notification = {**notification, 'click_action': _fcm_https_url(notification['click_action'])}
    data = {k: str(v) for k, v in fcm_notification.items()}
    return messaging.Message(
        notification=messaging.Notification(title=fcm_notification['title'], body=fcm_notification['body']),
        data=data,
        webpush=messaging.WebpushConfig(
            headers={'Urgency': 'high'},
            notification=messaging.WebpushNotification(
                title=fcm_notification['title'],
                body=fcm_notification['body'],
                icon=fcm_notification['icon'],
                badge=fcm_notification['icon'],
                tag=fcm_notification['tag'],
                require_interaction=True,
                data={k: str(v) for k, v in fcm_notification.items() if k in ('click_action', 'room_id', 'room_name', 'event_id', 'vote_id', 'citizen_id')},
            ),
            fcm_options=messaging.WebpushFCMOptions(link=fcm_notification['click_action']),
        ),
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
    'post': 'push_notifications_post',
    'task': 'push_notifications_task',
    'survey': 'push_notifications_survey',
    'bookkeeping': 'push_notifications_bookkeeping',
}


def get_push_event_config(event_key):
    """Return a validated event policy or None so unknown events fail closed."""
    events = getattr(settings, 'PUSH_EVENTS', {})
    config = events.get(event_key) if isinstance(events, dict) else None
    if not isinstance(config, dict) or config.get('module') not in _PUSH_FIELDS or any(type(config.get(channel)) is not bool for channel in ('fcm', 'websocket')):
        log.error('%s Unknown or invalid PUSH event configuration: %s', NOTIF_LOG_TAG, event_key)
        return None
    return config


def _push_enabled_for_user(user, notification_type):
    """Return True if the user has not disabled push for the given category."""
    if notifications_unsubscribed(user):
        return False
    if not notification_type:
        return True
    field = _PUSH_FIELDS.get(notification_type)
    if not field:
        return True
    try:
        return getattr(user.uzytkownik, field, True)
    except Exception:
        return True


def _push_muted_for_source(user, source_user_id):
    """Return whether the recipient muted the chat message author."""
    if not source_user_id:
        return False
    try:
        return user.uzytkownik.muted_push_users.filter(pk=source_user_id).exists()
    except Exception:
        return False


def _push_user_ids(notification_type):
    """Return active user IDs that have push enabled for the given category."""
    if not notification_type:
        return None
    field = _PUSH_FIELDS.get(notification_type)
    if not field:
        return None
    User = get_user_model()
    try:
        return set(User.objects.filter(is_active=True, uzytkownik__notifications_unsubscribed_at__isnull=True, **{f'uzytkownik__{field}': True}).values_list('id', flat=True))
    except DatabaseError as e:
        log.warning(f'{NOTIF_LOG_TAG} Failed to load push recipients for {notification_type}: {e}')
        return set()


def send_fcm_to_user_sync(user, notification, notification_type=None, source_user_id=None, push_event=None):
    """Send an FCM push notification to a single user's active devices."""
    notification_id = notification.get('notification_id', '?')
    if push_event:
        config = get_push_event_config(push_event)
        if not config or not config['fcm'] or (notification_type and notification_type != config['module']):
            return 0
        notification_type = config['module']
    if not _fcm_ready():
        log.warning(f"{NOTIF_LOG_TAG} FCM skipped for user {user.id} (notification_id={notification_id}): Firebase not initialized")
        return 0

    if not _push_enabled_for_user(user, notification_type):
        log.debug(f"{NOTIF_LOG_TAG} Push disabled for user {user.id} ({notification_type}), notification_id={notification_id}")
        return 0

    if _push_muted_for_source(user, source_user_id):
        log.debug(f"{NOTIF_LOG_TAG} Push muted for source user {source_user_id}, recipient {user.id}, notification_id={notification_id}")
        return 0

    _migrate_legacy_gcm_devices()
    fcm_devices = GCMDevice.objects.filter(user=user, active=True, cloud_message_type='FCM')
    try:
        profile = user.uzytkownik
        if not profile.push_phone_enabled:
            fcm_devices = fcm_devices.exclude(name__in=('mobile', 'tablet'))
        if not profile.push_computer_enabled:
            fcm_devices = fcm_devices.exclude(name='desktop')
    except Exception:
        pass
    device_count = fcm_devices.count()
    if not device_count:
        log.debug(f"{NOTIF_LOG_TAG} No FCM devices for user {user.id}, notification_id={notification_id}")
        return 0

    try:
        message = _build_fcm_message(notification)
        log.debug(f"{NOTIF_LOG_TAG} Sending FCM notification_id={notification_id} to user {user.id} ({device_count} device(s))")
        result = fcm_devices.send_message(message)
        if result and result.success_count > 0:
            log.info(f"{NOTIF_LOG_TAG} FCM sent {result.success_count}/{device_count} notification(s) to user {user.id}, notification_id={notification_id}")
        if result:
            for idx, resp in enumerate(result.responses):
                if not resp.success:
                    log.warning(f"{NOTIF_LOG_TAG} FCM response {idx} failed for user {user.id}, notification_id={notification_id}: {resp.exception}")
        return result.success_count if result else 0
    except Exception as e:
        log.error(f"{NOTIF_LOG_TAG} FCM failed for user {user.id}, notification_id={notification_id}: {e}", exc_info=True)
    return 0


def send_fcm_to_all_sync(notification, user_ids=None, notification_type=None):
    """Broadcast an FCM push notification to all active users or a subset of user IDs."""
    notification_id = notification.get('notification_id', '?')
    if not _fcm_ready():
        log.warning(f"{NOTIF_LOG_TAG} FCM broadcast skipped (notification_id={notification_id}): Firebase not initialized")
        return 0

    if user_ids is None and notification_type:
        user_ids = _push_user_ids(notification_type)

    if user_ids is not None and not user_ids:
        log.debug(f"{NOTIF_LOG_TAG} No push recipients for notification_id={notification_id}")
        return 0

    _migrate_legacy_gcm_devices()
    try:
        qs = GCMDevice.objects.filter(user__is_active=True, user__uzytkownik__notifications_unsubscribed_at__isnull=True, active=True, cloud_message_type='FCM').exclude(
            Q(name__in=('mobile', 'tablet'), user__uzytkownik__push_phone_enabled=False) | Q(name='desktop', user__uzytkownik__push_computer_enabled=False)
        )
        if user_ids is not None:
            qs = qs.filter(user_id__in=user_ids)
        if not qs.exists():
            log.debug(f"{NOTIF_LOG_TAG} No active FCM devices found (notification_id={notification_id})")
            return 0

        message = _build_fcm_message(notification)
        result = qs.send_message(message)
        if result and result.success_count > 0:
            log.info(f"{NOTIF_LOG_TAG} FCM broadcast sent {result.success_count} notification(s), notification_id={notification_id}")
        if result:
            for idx, resp in enumerate(result.responses):
                if not resp.success:
                    log.warning(f"{NOTIF_LOG_TAG} FCM broadcast response {idx} failed, notification_id={notification_id}: {resp.exception}")
        return result.success_count if result else 0
    except DatabaseError as e:
        log.error(f"{NOTIF_LOG_TAG} FCM broadcast skipped for notification_id={notification_id} due to DB error: {e}")
    except Exception as e:
        log.error(f"{NOTIF_LOG_TAG} FCM broadcast failed, notification_id={notification_id}: {e}", exc_info=True)
    return 0


def send_websocket_to_user_sync(user_id, notification, ws_type='notification', notification_type=None, push_event=None):
    """Send a WebSocket notification to a single user's personal group."""
    notification_id = notification.get('notification_id', '?')
    if push_event:
        config = get_push_event_config(push_event)
        if not config or not config['websocket'] or (notification_type and notification_type != config['module']):
            return
        notification_type = config['module']
    if notification_type:
        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if not user or not _push_enabled_for_user(user, notification_type):
            return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        log.warning(f"{NOTIF_LOG_TAG} Channel layer not configured; skipping WebSocket notification_id={notification_id} for user {user_id}")
        return

    try:
        log.debug(f"{NOTIF_LOG_TAG} group_send notification_id={notification_id} to user_{user_id} (type={ws_type})")
        event = {"type": ws_type, "notification": notification}
        if "room_id" in notification:
            event["room_id"] = notification["room_id"]
        async_to_sync(channel_layer.group_send)(f"user_{user_id}", event)
    except Exception as e:
        log.warning(f"{NOTIF_LOG_TAG} WebSocket notification_id={notification_id} failed for user {user_id}: {e}")


def send_websocket_to_all_sync(notification, ws_type='notification', notification_type=None, user_ids=None):
    """Broadcast a WebSocket notification to all active users' personal groups.

    Pass `user_ids` to reuse an already-computed set (e.g. from `send_notification_to_all_sync`)
    and skip a redundant preference lookup query.
    """
    notification_id = notification.get('notification_id', '?')
    channel_layer = get_channel_layer()
    if channel_layer is None:
        log.warning(f"{NOTIF_LOG_TAG} Channel layer not configured; skipping WebSocket broadcast, notification_id={notification_id}")
        return

    if user_ids is None:
        user_ids = _push_user_ids(notification_type)

    if user_ids is not None and not user_ids:
        log.debug(f"{NOTIF_LOG_TAG} No WebSocket recipients for notification_id={notification_id}")
        return

    User = get_user_model()
    queryset = User.objects.filter(is_active=True, uzytkownik__notifications_unsubscribed_at__isnull=True)
    if user_ids is not None:
        queryset = queryset.filter(id__in=user_ids)
    sent = 0
    for user_id in queryset.values_list('id', flat=True):
        try:
            async_to_sync(channel_layer.group_send)(f"user_{user_id}", {"type": ws_type, "notification": notification})
            sent += 1
        except Exception as e:
            log.warning(f"{NOTIF_LOG_TAG} WebSocket broadcast failed for user {user_id}, notification_id={notification_id}: {e}")
    log.debug(f"{NOTIF_LOG_TAG} WebSocket broadcast notification_id={notification_id} group_send to {sent} user(s)")


def send_notification_to_all_sync(notification, ws_type='notification', notification_type=None, *, send_push=True, send_websocket=True, recipient_ids=None):
    """Send both FCM and WebSocket notifications to active users."""
    if not (send_push or send_websocket):
        return
    try:
        user_ids = _push_user_ids(notification_type)
        if recipient_ids is not None:
            recipient_ids = set(recipient_ids)
            user_ids = recipient_ids if user_ids is None else user_ids & recipient_ids
        if send_push:
            send_fcm_to_all_sync(notification, user_ids=user_ids)
        if send_websocket:
            send_websocket_to_all_sync(notification, ws_type, user_ids=user_ids)
    except DatabaseError as e:
        log.error(f'{NOTIF_LOG_TAG} Broadcast notification skipped due to DB error: {e}')
    except Exception as e:
        log.error(f'{NOTIF_LOG_TAG} Broadcast notification failed: {e}', exc_info=True)


def send_notification_to_all_in_thread(notification, ws_type='notification', notification_type=None, daemon=True, *, send_push=True, send_websocket=True, recipient_ids=None):
    """Send both FCM and WebSocket notifications to active users in a background thread."""
    kwargs = {'ws_type': ws_type, 'notification_type': notification_type, 'send_push': send_push, 'send_websocket': send_websocket}
    if recipient_ids is not None:
        kwargs['recipient_ids'] = recipient_ids
    t = threading.Thread(target=send_notification_to_all_sync, args=(notification,), kwargs=kwargs, daemon=daemon)
    t.start()
    return t


def _claim_post_update_notification(post_id):
    """Claim the 90-minute notification window for a post update."""
    try:
        instance = get_site_domain()
        key = f'notification-throttle:{instance}:post:{post_id}:updated'
        claimed = cache.add(key, True, timeout=settings.NOTIFICATION_THROTTLE_SECONDS)
    except Exception as error:
        log.warning(f'{NOTIF_LOG_TAG} Post update throttling unavailable; sending notification: {error}')
        return True

    if not claimed:
        log.debug(f'{NOTIF_LOG_TAG} Skipping repeated post update notification for post {post_id}')
    return claimed


def _dispatch_notification(title, body, click_action, tag, **kwargs):
    """Central helper used by domain-signal receivers to send FCM, WebSocket and/or email.

    Remaining keyword arguments are treated as extra payload keys for FCM/WebSocket
    notifications (e.g. `vote_id`, `citizen_id`).
    """
    notification_type = kwargs.pop('notification_type', None)
    push_event = kwargs.pop('push_event', None)
    recipient_ids = kwargs.pop('recipient_ids', None)
    ws_type = kwargs.pop('ws_type', 'notification')
    email_subject = kwargs.pop('email_subject', None) or title
    email_body = kwargs.pop('email_body', None) or body
    recipient_email = kwargs.pop('recipient_email', None)
    recipient_user = kwargs.pop('recipient_user', None)
    recipient_subject = kwargs.pop('recipient_subject', None)
    recipient_body = kwargs.pop('recipient_body', None)
    send_push = kwargs.pop('send_push', True)
    send_websocket = kwargs.pop('send_websocket', True)
    send_email = kwargs.pop('send_email', True)
    if push_event:
        config = get_push_event_config(push_event)
        if not config or (notification_type and notification_type != config['module']):
            send_push = send_websocket = False
        else:
            notification_type = config['module']
            send_push = send_push and config['fcm']
            send_websocket = send_websocket and config['websocket']
    transactional = kwargs.pop('transactional', False)
    in_thread = kwargs.pop('in_thread', True)
    daemon = kwargs.pop('daemon', True)
    strip_html = kwargs.pop('strip_html', False)
    log_prefix = kwargs.pop('log_prefix', '')
    sleep_before = kwargs.pop('sleep_before', 0)
    raise_on_error = kwargs.pop('raise_on_error', False)
    extra = kwargs

    if strip_html:
        title = strip_tags(title)
        body = strip_tags(body)
        email_subject = strip_tags(email_subject)
        email_body = strip_tags(email_body)
        if recipient_subject:
            recipient_subject = strip_tags(recipient_subject)
        if recipient_body:
            recipient_body = strip_tags(recipient_body)

    log_tag = f"{log_prefix}{NOTIF_LOG_TAG}"

    notification = None
    if send_push or send_websocket:
        notification = build_notification(title, body, click_action, tag, **extra)
        delivery_options = {'ws_type': ws_type, 'notification_type': notification_type, 'send_push': send_push, 'send_websocket': send_websocket}
        if recipient_ids is not None:
            delivery_options['recipient_ids'] = recipient_ids
        if in_thread:
            send_notification_to_all_in_thread(notification, daemon=daemon, **delivery_options)
        else:
            send_notification_to_all_sync(notification, **delivery_options)

    if sleep_before:
        time.sleep(sleep_before)

    if send_email and recipient_email and (transactional or not notifications_unsubscribed(recipient_user)):
        subject = recipient_subject or email_subject
        message = recipient_body or email_body
        try:
            with override(get_user_language(recipient_user) if recipient_user else settings.LANGUAGE_CODE):
                mail_options = {'headers': unsubscribe_headers(recipient_user)} if not transactional and recipient_user else {}
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient_email], fail_silently=False, **mail_options)
            log.debug(f'{log_tag} Email sent to {recipient_email}; subject: {subject}')
        except Exception as e:
            log.error(f'{log_tag} Failed to send email to {recipient_email}: {e}', exc_info=True)
            if raise_on_error:
                raise


@receiver(citizen_proposed)
def on_citizen_proposed(sender, candidate, proposed_by=None, **kwargs):
    """Notify opted-in users when a new candidate is proposed."""
    title = _('New citizen proposed')
    body = f'{candidate.get_full_name() or candidate.username}\n{build_site_url("/obywatele/poczekalnia/")}'
    _dispatch_notification(title, body, '/obywatele/poczekalnia/', f'citizen-proposed-{candidate.id}', push_event='citizen.proposed', ws_type='citizen.notification', send_email=False, citizen_id=candidate.id)


@receiver(citizen_accepted)
def on_citizen_accepted(sender, user, **kwargs):
    """Send a welcome email to the freshly-activated citizen."""
    kwargs.pop('signal', None)
    recipient_email = kwargs.pop('recipient_email', None) or (user.email if user else None)
    recipient_subject = kwargs.pop('recipient_subject', None)
    recipient_body = kwargs.pop('recipient_body', None)
    sleep_before = kwargs.pop('sleep_before', 0)

    if not (recipient_email and recipient_subject and recipient_body):
        return

    _dispatch_notification(
        recipient_subject,
        recipient_body,
        '',
        f'citizen-accepted-{user.id}',
        notification_type='obywatele',
        push_event='citizen.accepted',
        ws_type='citizen.notification',
        recipient_ids={user.id},
        send_email=True,
        recipient_email=recipient_email,
        recipient_user=user,
        recipient_subject=recipient_subject,
        recipient_body=recipient_body,
        transactional=True,
        sleep_before=sleep_before,
    )


@receiver(citizen_blocked)
def on_citizen_blocked(sender, user, was_previously_active=False, title=None, body=None, click_action=None, tag=None, strip_html=False, **kwargs):
    if not (was_previously_active and title and body and click_action and tag):
        return

    recipient_ids = _push_user_ids('obywatele') - {user.id}
    _dispatch_notification(
        title,
        body,
        click_action,
        tag,
        notification_type='obywatele',
        push_event='citizen.blocked',
        ws_type='citizen.notification',
        send_email=False,
        in_thread=False,
        recipient_ids=recipient_ids,
        strip_html=strip_html,
        citizen_id=user.id,
    )


_VOTE_PUSH_EVENTS = {
    'proposed': 'vote.proposed',
    'modified': 'vote.modified',
    'discussion_started': 'vote.discussion_started',
    'started': 'vote.started',
    'approved': 'vote.approved',
    'rejected': 'vote.rejected',
    'rejected_no_signatures': 'vote.rejected_no_signatures',
    'last_day': 'vote.last_day',
    'buffer_restart': 'vote.buffer_restarted',
}


@receiver(vote_started)
@receiver(vote_state_changed)
def on_vote_notification(sender, **kwargs):
    """Dispatch vote notifications through their event-specific PUSH policy."""
    kwargs.pop('signal', None)
    kwargs.pop('decyzja', None)
    transition = kwargs.pop('transition', None)

    kwargs.setdefault('notification_type', 'glosowania')
    kwargs.setdefault('ws_type', 'vote.notification')
    kwargs.setdefault('in_thread', False)
    kwargs.setdefault('daemon', False)
    kwargs.setdefault('send_email', False)
    push_event = _VOTE_PUSH_EVENTS.get(transition)
    if push_event:
        kwargs['push_event'] = push_event
        kwargs.setdefault('send_push', True)
        kwargs.setdefault('send_websocket', True)
    else:
        kwargs['send_push'] = False
        kwargs['send_websocket'] = False

    if 'title' in kwargs and 'body' in kwargs and 'click_action' in kwargs and 'tag' in kwargs:
        _dispatch_notification(kwargs.pop('title'), kwargs.pop('body'), kwargs.pop('click_action'), kwargs.pop('tag'), **kwargs)


@receiver(vote_argument_added)
def on_vote_argument_added(sender, argument, **kwargs):
    decision = argument.decyzja
    url = build_site_url(f'/glosowania/details/{decision.id}')
    title = _('New argument added to a voting proposal')
    body = f'{decision.title}: {argument.get_argument_type_display()}\n{url}'
    _dispatch_notification(
        title,
        body,
        url,
        f'vote-argument-{argument.id}',
        notification_type='glosowania',
        push_event='vote.argument_added',
        ws_type='vote.notification',
        send_email=False,
        vote_id=decision.id,
        argument_id=argument.id,
    )


@receiver(event_created)
def on_event_created(sender, event, url, **kwargs):
    title = _('New event created')
    body = f'{event.title}\n{url}'
    _dispatch_notification(title, body, url, f'event-created-{event.id}', push_event='event.created', ws_type='event.notification', send_email=False, event_id=event.id)


@receiver(event_updated)
def on_event_updated(sender, event, url, **kwargs):
    title = _('Calendar event updated')
    body = f'{event.title}\n{url}'
    _dispatch_notification(title, body, url, f'event-updated-{event.id}', push_event='event.updated', ws_type='event.notification', send_email=False, event_id=event.id)


@receiver(event_starting)
def on_event_starting(sender, event, body=None, **kwargs):
    """Notify all active users that an event is about to start."""
    click_action = event.link or build_site_url(event.get_absolute_url())

    if body:
        notification_body = body
    else:
        start = formats.localize(event.start_date, use_l10n=True)
        notification_body = html.unescape(str(start)).replace('\xa0', ' ')
        if event.place:
            notification_body = f"{notification_body} | {event.place}"
        if event.description:
            description = re.sub(r'(?i)<br\s*/?>', '\n', html.unescape(str(event.description))).replace('\xa0', ' ')
            notification_body = f"{notification_body}\n\n{description}"

    title = f"{event.title} — {_('starting now')}"
    _dispatch_notification(
        title,
        notification_body,
        click_action,
        f'event-{event.id}',
        notification_type='events',
        push_event='event.starting',
        ws_type='event.notification',
        email_subject=title,
        email_body=f"{notification_body}\n\n{click_action}",
        send_push=True,
        send_websocket=True,
        send_email=False,
        in_thread=False,
        event_id=event.id,
    )


@receiver(task_created)
def on_task_created(sender, task, url, **kwargs):
    """Notify opted-in users about a newly created task."""
    title = _('New activity created')
    body = f'{task.title}\n{url}'
    _dispatch_notification(title, body, url, f'task-{task.id}', notification_type='task', push_event='task.created', ws_type='task.notification', send_email=False, task_id=task.id)


@receiver(task_helper_joined)
def on_task_helper_joined(sender, task, helper, coordinator_id, **kwargs):
    """Notify the coordinator when someone volunteers to help with their task."""
    if coordinator_id == helper.id:
        return
    url = build_site_url(f'/tasks/{task.id}/')
    title = _('Someone wants to help with your activity')
    body = f'{helper.get_full_name() or helper.username}\n{task.title}\n{url}'
    _dispatch_notification(
        title,
        body,
        url,
        f'task-helper-{task.id}-{helper.id}',
        notification_type='task',
        push_event='task.helper_joined',
        ws_type='task.notification',
        send_email=False,
        recipient_ids={coordinator_id},
        task_id=task.id,
    )


@receiver(task_status_changed)
def on_task_status_changed(sender, task, previous_status, **kwargs):
    """Notify the coordinator when their task changes status."""
    if not task.assigned_to_id:
        return
    url = build_site_url(f'/tasks/{task.id}/')
    title = _('Activity status changed')
    body = f'{task.title}: {task.get_status_display()}\n{url}'
    _dispatch_notification(
        title,
        body,
        url,
        f'task-status-{task.id}-{task.status}',
        notification_type='task',
        push_event='task.status_changed',
        ws_type='task.notification',
        send_email=False,
        recipient_ids={task.assigned_to_id},
        task_id=task.id,
    )


@receiver(document_created)
def on_document_created(sender, post, url, **kwargs):
    title = _('New document created')
    body = f'{post.title}\n{url}'
    _dispatch_notification(title, body, url, f'document-created-{post.id}', notification_type='post', push_event='document.created', ws_type='post.notification', send_email=False, post_id=post.id)


@receiver(important_post_published)
def on_important_post_published(sender, post, url, created=False, **kwargs):
    """Notify all active users about an important board post."""
    if not created and not _claim_post_update_notification(post.id):
        return
    if created:
        title = _('Important post published')
    else:
        title = _('Important post updated')
    if post.author:
        author = post.author.get_full_name() or post.author.username
    else:
        author = _('System')
    display_title = getattr(post, 'get_display_title', None)
    display_title = display_title() if callable(display_title) else post.title
    body = f'{display_title}\n{_("by")} {author}\n{url}'
    _dispatch_notification(
        title,
        body,
        url,
        f'post-{post.id}',
        notification_type='post',
        push_event='document.important_updated' if not created else None,
        ws_type='post.notification',
        email_subject=title,
        email_body=body,
        send_push=not created,
        send_websocket=not created,
        send_email=False,
        post_id=post.id,
    )


@receiver(transaction_created)
def on_transaction_created(sender, transaction, url, **kwargs):
    title = _('New financial transaction')
    body = f'{transaction.get_type_display()}: {transaction.amount} {transaction.asset.symbol}\n{transaction.partner}\n{url}'
    _dispatch_notification(
        title, body, url, f'transaction-{transaction.id}', notification_type='bookkeeping', push_event='transaction.created', ws_type='transaction.notification', send_email=False, transaction_id=transaction.id
    )


@receiver(transaction_updated)
def on_transaction_updated(sender, transaction, url, **kwargs):
    title = _('Financial transaction updated')
    body = f'{transaction.get_type_display()}: {transaction.amount} {transaction.asset.symbol}\n{transaction.partner}\n{url}'
    _dispatch_notification(
        title,
        body,
        url,
        f'transaction-updated-{transaction.id}',
        notification_type='bookkeeping',
        push_event='transaction.updated',
        ws_type='transaction.notification',
        send_email=False,
        transaction_id=transaction.id,
    )


@receiver(survey_created)
def on_survey_created(sender, survey, url, **kwargs):
    """Notify all active users about a newly created survey."""
    title = _('New survey created')
    body = f'{survey.title}\n{url}'
    _dispatch_notification(
        title,
        body,
        url,
        f'survey-{survey.id}',
        notification_type='survey',
        push_event='survey.created',
        ws_type='survey.notification',
        email_subject=title,
        email_body=body,
        send_email=False,
        survey_id=survey.id,
    )


@receiver(survey_updated)
def on_survey_updated(sender, survey, url, **kwargs):
    title = _('Survey updated')
    body = f'{survey.title}\n{url}'
    _dispatch_notification(title, body, url, f'survey-updated-{survey.id}', notification_type='survey', push_event='survey.updated', ws_type='survey.notification', send_email=False, survey_id=survey.id)


class WikikracjaPushConfig:
    """Config adapter for django-push-notifications.

    The project uses GCMDevice.application_id only to store the PWA display mode
    (browser/standalone/minimal-ui/fullscreen). All devices share the same
    Firebase project, so this adapter ignores application_id and always returns
    the global FIREBASE_APP and FCM_MAX_RECIPIENTS from PUSH_NOTIFICATIONS_SETTINGS.
    """

    def get_firebase_app(self, application_id=None):
        return settings.PUSH_NOTIFICATIONS_SETTINGS.get("FIREBASE_APP")

    def get_max_recipients(self, application_id=None):
        return settings.PUSH_NOTIFICATIONS_SETTINGS.get("FCM_MAX_RECIPIENTS", 1000)
