import logging

from django.core.management.base import BaseCommand

from chat.services import ensure_system_rooms

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ensure the system chat rooms Inbox and Ważne exist.'

    def handle(self, *args, **options):
        rooms = ensure_system_rooms()
        log.info('System chat rooms ready: %s.', ', '.join(room.title for room in rooms.values()))
