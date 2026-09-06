import logging

from core.signals import event_starting

log = logging.getLogger(__name__)


def notify_event_starting(event, body=None):
    """Emit the event_starting domain signal; the central dispatcher sends FCM, WebSocket and email."""
    event_starting.send(sender='events.services', event=event, body=body)
    log.info(f'event_starting signal sent for event {event.id}')
