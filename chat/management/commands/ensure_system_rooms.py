from django.core.management.base import BaseCommand

from chat.services import ensure_system_rooms


class Command(BaseCommand):
    help = 'Ensure the system chat rooms Inbox and Ważne exist.'

    def handle(self, *args, **options):
        rooms = ensure_system_rooms()
        self.stdout.write(f"System chat rooms ready: {', '.join(room.title for room in rooms.values())}.")
