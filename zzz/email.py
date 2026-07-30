"""Helpers for sending bulk emails asynchronously."""
import logging
import threading
import time

from django.conf import settings as s
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.utils.translation import gettext_lazy as _

from zzz.richtext import strip_tags
from zzz.utils import build_site_url, get_site_domain

log = logging.getLogger(__name__)


def send_bulk_email_in_thread(
    recipients,
    subject,
    body,
    *,
    from_email=None,
    fail_silently=False,
    sleep_before=0,
    per_recipient_sleep=0,
    raise_on_error=True,
    log_prefix="",
    daemon=True,
):
    """Send the same email to a list of recipients in a background thread.

    Args:
        recipients: Iterable of email addresses or a callable returning one.
        subject: Email subject (already localized/formatted).
        body: Email body (already localized/formatted).
        from_email: Sender address (defaults to settings.DEFAULT_FROM_EMAIL).
        fail_silently: Passed to EmailMessage.send().
        sleep_before: Seconds to sleep before starting to send.
        per_recipient_sleep: Seconds to sleep after each recipient.
        raise_on_error: If False, log errors per recipient and continue sending.
        log_prefix: Optional prefix added to log messages.
        daemon: Whether the background thread should be a daemon thread.
    Returns:
        threading.Thread: The started thread.
    """
    if from_email is None:
        from_email = str(s.DEFAULT_FROM_EMAIL)

    def _send():
        try:
            time.sleep(sleep_before)
            recipient_list = recipients() if callable(recipients) else recipients
            for recipient in recipient_list:
                try:
                    email_message = EmailMessage(
                        from_email=from_email,
                        to=[recipient],
                        subject=subject,
                        body=body,
                    )
                    email_message.send(fail_silently=fail_silently)
                    log.info(f"{log_prefix}Email sent to {recipient}; subject: {subject}")
                except Exception as e:
                    log.error(f"{log_prefix}Failed to send email to {recipient}; subject: {subject}; error: {e}", exc_info=True)
                    if raise_on_error:
                        raise
                time.sleep(per_recipient_sleep)
            log.info(f"{log_prefix}All emails sent successfully; subject: {subject}")
        except Exception as e:
            log.error(f"{log_prefix}Failed to send email; subject: {subject}; error: {e}", exc_info=True)

    t = threading.Thread(target=_send)
    t.daemon = daemon
    t.start()
    return t


def send_notification_email_to_active_users(
    subject,
    message,
    notification_type=None,
    *,
    strip_html=False,
    log_prefix="",
    **thread_kwargs,
):
    """Send a notification email to active users filtered by notification preference.

    Args:
        subject: Custom subject string.
        message: Custom body string.
        notification_type: 'obywatele', 'glosowania', 'chat' or None (all active users).
        strip_html: If True, strip HTML tags from the message before sending.
        log_prefix: Optional prefix for log messages.
    """
    from django.utils import translation

    translation.activate(s.LANGUAGE_CODE)
    HOST = get_site_domain()

    settings_url = build_site_url('/obywatele/settings/')
    email_footer = _("You can manage your email notifications here: {url}").format(url=settings_url)

    if strip_html:
        message = strip_tags(message)

    def _get_recipients():
        User = get_user_model()
        if notification_type == 'obywatele':
            return list(User.objects.filter(is_active=True, uzytkownik__email_notifications_obywatele=True).values_list('email', flat=True))
        elif notification_type == 'glosowania':
            return list(User.objects.filter(is_active=True, uzytkownik__email_notifications_glosowania=True).values_list('email', flat=True))
        elif notification_type == 'chat':
            return list(User.objects.filter(is_active=True, uzytkownik__email_notifications_chat=True).values_list('email', flat=True))
        elif notification_type == 'events':
            return list(User.objects.filter(is_active=True, uzytkownik__email_notifications_events=True).values_list('email', flat=True))
        else:
            return list(User.objects.filter(is_active=True).values_list('email', flat=True))

    log.info(f'{log_prefix}Sending email to active users; subject: {subject}')
    return send_bulk_email_in_thread(
        _get_recipients,
        subject=f'[{HOST}] {subject}',
        body=f"{message}\n\n{email_footer}",
        fail_silently=False,
        sleep_before=s.EMAIL_SEND_DELAY_SECONDS,
        per_recipient_sleep=s.EMAIL_SEND_DELAY_SECONDS,
        log_prefix=log_prefix,
        **thread_kwargs,
    )
