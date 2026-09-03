from django.core.management.base import BaseCommand

from chat.models import Room


class Command(BaseCommand):
    help = 'Ensure the guest-facing Inbox room exists and contains its welcome message.'

    def handle(self, *args, **options):
        from site_settings.params import get_param

        if not get_param('group_is_public'):
            self.stdout.write(self.style.WARNING('GROUP_IS_PUBLIC is False; skipping Inbox creation.'))
            return

        already_exists = Room.objects.filter(is_inbox=True).exists()
        room = Room.create_inbox()
        if room is None:
            self.stdout.write(self.style.WARNING('Could not create Inbox room.'))
            return

        if already_exists:
            self.stdout.write(self.style.SUCCESS('Inbox room already exists.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created Inbox room (id={room.id}).'))
