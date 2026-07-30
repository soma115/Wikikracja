import logging

from django.utils.translation import gettext as _
from zzz.email import send_notification_email_to_active_users
from zzz.notifications import build_notification, send_notification_to_all_sync
from zzz.utils import get_site_domain

log = logging.getLogger(__name__)
domain = get_site_domain()


def build_event_notification(event, body=None, reminder=False):
    """Build a notification payload for an event."""
    site_url = f"https://{domain}"
    click_action = event.link if event.link else f"{site_url}{event.get_absolute_url()}"

    if reminder:
        title = f"{event.title} — {_('starting now')}"
    else:
        title = event.title

    if body is None:
        from django.utils import formats
        body = formats.localize(event.start_date, use_l10n=True)

    return build_notification(
        title,
        body,
        click_action,
        f"event-{event.id}",
        event_id=event.id,
    )


def notify_event_starting(event, body=None):
    """Send FCM, WebSocket and email notifications for an event."""
    notification = build_event_notification(event, body=body, reminder=True)
    send_notification_to_all_sync(notification, ws_type='event.notification', notification_type='events')

    subject = f"{event.title} — {_('starting now')}"
    message = body if body else notification['body']
    send_notification_email_to_active_users(
        subject,
        f"{message}\n\n{notification['click_action']}",
        notification_type='events',
        log_prefix='events: ',
    )
