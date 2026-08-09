from django.core.management.base import BaseCommand

from chat.models import Room


class Command(BaseCommand):
    help = 'Create the guest-facing Inbox room if it does not exist.'

    def handle(self, *args, **options):
        from site_settings.params import get_param

        if not get_param('group_is_public'):
            self.stdout.write(self.style.WARNING('GROUP_IS_PUBLIC is False; skipping Inbox creation.'))
            return
        if Room.objects.filter(is_inbox=True).exists():
            self.stdout.write(self.style.SUCCESS('Inbox room already exists.'))
            return
        room = Room.create_inbox()
        self.stdout.write(self.style.SUCCESS(f'Created Inbox room (id={room.id}).'))
