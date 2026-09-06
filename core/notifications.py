import html
import logging
import os
import re
import threading
import time
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q
from django.db.utils import DatabaseError
from django.dispatch import receiver
from django.utils import formats
from django.utils.translation import gettext as _
from firebase_admin import messaging
from push_notifications.models import GCMDevice

from core.richtext import strip_tags
from core.signals import citizen_accepted, citizen_blocked, citizen_proposed, event_starting, important_post_published, survey_created, task_created, vote_started, vote_state_changed
from core.utils import build_site_url
from site_settings.models import SiteSettings
from site_settings.services import get_branding_version

log = logging.getLogger(__name__)

# Prefix for every log line in the notification build/send/receive pipeline so the
# whole journey of a notification can be found with a single search — in server logs
# and in the browser console (see chat/static/chat/js/*.js, which use the same tag) —
# regardless of which of the many code paths (FCM, WebSocket, chat, events, votes,
# citizens...) it went through.
NOTIF_LOG_TAG = "[NOTIFDBG]"


def _icon_url():
    ss = SiteSettings.get()
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
                data={k: str(v) for k, v in notification.items() if k in ('click_action', 'room_id', 'room_name', 'event_id', 'vote_id', 'citizen_id')},
            ),
            fcm_options=messaging.WebpushFCMOptions(link=notification['click_action']),
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
    try:
        return set(User.objects.filter(is_active=True, **{f'uzytkownik__{field}': True}).values_list('id', flat=True))
    except DatabaseError as e:
        log.warning(f'{NOTIF_LOG_TAG} Failed to load push recipients for {notification_type}: {e}')
        return set()


def send_fcm_to_user_sync(user, notification, notification_type=None):
    """Send an FCM push notification to a single user's active devices."""
    notification_id = notification.get('notification_id', '?')
    if not _fcm_ready():
        log.warning(f"{NOTIF_LOG_TAG} FCM skipped for user {user.id} (notification_id={notification_id}): Firebase not initialized")
        return 0

    if not _push_enabled_for_user(user, notification_type):
        log.debug(f"{NOTIF_LOG_TAG} Push disabled for user {user.id} ({notification_type}), notification_id={notification_id}")
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
        qs = GCMDevice.objects.filter(user__is_active=True, active=True, cloud_message_type='FCM').exclude(
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


def send_websocket_to_user_sync(user_id, notification, ws_type='notification'):
    """Send a WebSocket notification to a single user's personal group."""
    notification_id = notification.get('notification_id', '?')
    channel_layer = get_channel_layer()
    if channel_layer is None:
        log.warning(f"{NOTIF_LOG_TAG} Channel layer not configured; skipping WebSocket notification_id={notification_id} for user {user_id}")
        return

    try:
        log.debug(f"{NOTIF_LOG_TAG} group_send notification_id={notification_id} to user_{user_id} (type={ws_type})")
        async_to_sync(channel_layer.group_send)(f"user_{user_id}", {"type": ws_type, "notification": notification})
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
    queryset = User.objects.filter(is_active=True)
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


def send_notification_to_all_sync(notification, ws_type='notification', notification_type=None, *, send_push=True, send_websocket=True):
    """Send both FCM and WebSocket notifications to all active users."""
    if not (send_push or send_websocket):
        return
    try:
        user_ids = _push_user_ids(notification_type)
        if send_push:
            send_fcm_to_all_sync(notification, user_ids=user_ids)
        if send_websocket:
            send_websocket_to_all_sync(notification, ws_type, user_ids=user_ids)
    except DatabaseError as e:
        log.error(f'{NOTIF_LOG_TAG} Broadcast notification skipped due to DB error: {e}')


def send_notification_to_all_in_thread(notification, ws_type='notification', notification_type=None, daemon=True, *, send_push=True, send_websocket=True):
    """Send both FCM and WebSocket notifications to all active users in a background thread.

    Use this from request-handling code paths (views, forms) so the HTTP response doesn't
    block on the WebSocket broadcast loop (one channel-layer round trip per active user).
    Mirrors the pattern used by `send_bulk_email_in_thread` for emails. Management commands
    that already run out-of-band can keep using `send_notification_to_all_sync` directly.
    """
    t = threading.Thread(
        target=send_notification_to_all_sync, args=(notification,), kwargs={'ws_type': ws_type, 'notification_type': notification_type, 'send_push': send_push, 'send_websocket': send_websocket}, daemon=daemon
    )
    t.start()
    return t


def _dispatch_notification(title, body, click_action, tag, **kwargs):
    """Central helper used by domain-signal receivers to send FCM, WebSocket and/or email.

    Remaining keyword arguments are treated as extra payload keys for FCM/WebSocket
    notifications (e.g. `vote_id`, `citizen_id`).
    """
    notification_type = kwargs.pop('notification_type', None)
    ws_type = kwargs.pop('ws_type', 'notification')
    email_subject = kwargs.pop('email_subject', None) or title
    email_body = kwargs.pop('email_body', None) or body
    recipient_email = kwargs.pop('recipient_email', None)
    recipient_subject = kwargs.pop('recipient_subject', None)
    recipient_body = kwargs.pop('recipient_body', None)
    send_push = kwargs.pop('send_push', True)
    send_websocket = kwargs.pop('send_websocket', True)
    send_email = kwargs.pop('send_email', True)
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
        if in_thread:
            send_notification_to_all_in_thread(notification, ws_type=ws_type, notification_type=notification_type, daemon=daemon, send_push=send_push, send_websocket=send_websocket)
        else:
            send_notification_to_all_sync(notification, ws_type=ws_type, notification_type=notification_type, send_push=send_push, send_websocket=send_websocket)

    if sleep_before:
        time.sleep(sleep_before)

    if send_email and recipient_email:
        subject = recipient_subject or email_subject
        message = recipient_body or email_body
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient_email], fail_silently=False)
            log.debug(f'{log_tag} Email sent to {recipient_email}; subject: {subject}')
        except Exception as e:
            log.error(f'{log_tag} Failed to send email to {recipient_email}: {e}', exc_info=True)
            if raise_on_error:
                raise


@receiver(citizen_proposed)
def on_citizen_proposed(sender, candidate, proposed_by=None, **kwargs):
    """Notify all active users that a new citizen has been proposed or signed up."""
    if proposed_by:
        title = _('New citizen has been proposed')
        body = f'{proposed_by.username} {_("proposed new citizen")}'
        click_action = build_site_url(f'/obywatele/poczekalnia/{candidate.id}')
        tag = f'citizen-{candidate.id}'
    else:
        title = _('New person requested membership')
        body = _('User %(username)s just requested membership') % {'username': candidate.username}
        click_action = build_site_url('/obywatele/poczekalnia/')
        tag = f'citizen-signup-{candidate.id}'

    email_body = f'{body}\n{click_action}'
    if proposed_by:
        email_body = f'{body}\n{_("You can approve him/her here:")} {click_action}'

    _dispatch_notification(
        title,
        body,
        click_action,
        tag,
        notification_type='obywatele',
        ws_type='citizen.notification',
        email_subject=title,
        email_body=email_body,
        send_push=True,
        send_websocket=True,
        send_email=False,
        citizen_id=candidate.id,
    )


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
        ws_type='citizen.notification',
        send_push=False,
        send_websocket=False,
        send_email=True,
        recipient_email=recipient_email,
        recipient_subject=recipient_subject,
        recipient_body=recipient_body,
        sleep_before=sleep_before,
    )


@receiver(citizen_blocked)
def on_citizen_blocked(sender, user, **kwargs):
    """Notify the blocked citizen personally and broadcast the ban to active users."""
    title = kwargs.pop('title', '')
    body = kwargs.pop('body', '')
    click_action = kwargs.pop('click_action', '')
    tag = kwargs.pop('tag', '')
    recipient_subject = kwargs.pop('recipient_subject', None)
    recipient_body = kwargs.pop('recipient_body', None)
    recipient_email = kwargs.pop('recipient_email', None)
    sleep_before = kwargs.pop('sleep_before', 0)
    kwargs.pop('was_previously_active', None)

    # Personal email to the banned citizen
    recipient = recipient_email or (user.email if user else None)
    if recipient and recipient_subject and recipient_body:
        _dispatch_notification(
            recipient_subject,
            recipient_body,
            '',
            f'citizen-blocked-{user.id}',
            notification_type='obywatele',
            ws_type='citizen.notification',
            send_push=False,
            send_websocket=False,
            send_email=True,
            recipient_email=recipient,
            recipient_subject=recipient_subject,
            recipient_body=recipient_body,
            sleep_before=sleep_before,
        )

    # Broadcast notification to remaining active users
    if title and body and click_action and tag:
        _dispatch_notification(
            title,
            body,
            click_action,
            tag,
            notification_type='obywatele',
            ws_type='citizen.notification',
            send_push=True,
            send_websocket=True,
            send_email=False,
            in_thread=False,
            daemon=False,
            strip_html=True,
            citizen_id=user.id if user else None,
        )


@receiver(vote_started)
@receiver(vote_state_changed)
def on_vote_notification(sender, **kwargs):
    """Dispatch vote-related notifications using the payload supplied by the sender."""
    # Pop domain objects that should not leak into FCM/WebSocket payloads.
    kwargs.pop('signal', None)
    kwargs.pop('decyzja', None)
    kwargs.pop('transition', None)

    # Defaults for vote notifications emitted from management commands.
    kwargs.setdefault('notification_type', 'glosowania')
    kwargs.setdefault('ws_type', 'vote.notification')
    kwargs.setdefault('in_thread', False)
    kwargs.setdefault('daemon', False)
    # Digest emails are sent once daily; do not send immediate vote emails.
    kwargs.setdefault('send_email', False)

    if 'title' in kwargs and 'body' in kwargs and 'click_action' in kwargs and 'tag' in kwargs:
        _dispatch_notification(kwargs.pop('title'), kwargs.pop('body'), kwargs.pop('click_action'), kwargs.pop('tag'), **kwargs)


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
    """Notify all active users about a newly created task."""
    title = _('New activity created')
    body = f'{task.title}\n{url}'
    _dispatch_notification(
        title, body, url, f'task-{task.id}', notification_type='task', ws_type='task.notification', email_subject=title, email_body=body, send_push=True, send_websocket=True, send_email=False, task_id=task.id
    )


@receiver(important_post_published)
def on_important_post_published(sender, post, url, created=False, **kwargs):
    """Notify all active users about an important board post."""
    if created:
        title = _('Important post published')
    else:
        title = _('Important post updated')
    author = post.author.username if post.author else _('System')
    body = f'{post.title}\n{_("by")} {author}\n{url}'
    _dispatch_notification(
        title, body, url, f'post-{post.id}', notification_type='post', ws_type='post.notification', email_subject=title, email_body=body, send_push=True, send_websocket=True, send_email=False, post_id=post.id
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
        ws_type='survey.notification',
        email_subject=title,
        email_body=body,
        send_push=True,
        send_websocket=True,
        send_email=False,
        survey_id=survey.id,
    )
