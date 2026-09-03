"""Helpers for sending bulk emails asynchronously."""

import logging
import threading
import time

from django.conf import settings as s
from django.core.mail import EmailMessage, EmailMultiAlternatives

log = logging.getLogger(__name__)


def send_bulk_email_in_thread(recipients, subject, body, *, html_message=None, from_email=None, fail_silently=False, sleep_before=0, per_recipient_sleep=0, raise_on_error=True, log_prefix="", daemon=True):
    """Send the same email to a list of recipients in a background thread.

    Args:
        recipients: Iterable of email addresses or a callable returning one.
        subject: Email subject (already localized/formatted).
        body: Plain-text email body (already localized/formatted).
        html_message: Optional HTML alternative body.
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
                    if html_message:
                        email_message = EmailMultiAlternatives(from_email=from_email, to=[recipient], subject=subject, body=body)
                        email_message.attach_alternative(html_message, 'text/html')
                    else:
                        email_message = EmailMessage(from_email=from_email, to=[recipient], subject=subject, body=body)
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
