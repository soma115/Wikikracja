import logging
from datetime import timedelta as td

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import Message, Room

log = logging.getLogger(__name__)


# chat_rooms command
class Command(BaseCommand):
    help = 'Create/Delete/Archive chat rooms'

    def handle(self, *args, **options):
        ts = timezone.now().strftime('%Y-%m-%d %H:%M:%S%z')
        self.stdout.write(f'[{ts}] Starting chat_rooms command...')

        # Allow active user access to all public rooms
        public_rooms = Room.objects.filter(public=True)
        private_rooms = Room.objects.filter(public=False)
        active_users = User.objects.filter(is_active=True)

        for pr in public_rooms:
            pr.allowed.set(active_users)

        # create_one2one_rooms(user_accepted)  # use it if there is no private rooms

        # Archive/Delete old public chat rooms
        from site_settings.params import get_param

        archive_after = get_param('archive_public_chat_room')
        delete_after = get_param('delete_public_chat_room')
        for room in public_rooms:
            try:
                last_message = Message.objects.filter(room_id=room.id).latest('time')
            except (Message.DoesNotExist):
                # logger.info(f'Message.DoesNotExist1 in {room}')
                continue
            if last_message.time < (timezone.now() - td(days=archive_after)):  # archive public after 3 months
                log.info(f'Chat room {room.title} archived.')
                room.archived = True  # archive
                room.save()
            elif last_message.time > (timezone.now() - td(days=archive_after)):  # unarchive
                room.archived = False  # unarchive
                room.save()

            # Skip deletion for protected rooms (for tasks, voting) - they should only be deleted when the task/vote is deleted
            if room.protected:
                continue

            if last_message.time < (timezone.now() - td(days=delete_after)):  # delete after 1 year
                log.info(f'Chat room {room.title} deleted.')
                room.delete()  # delete
                room.save()

        # Archive/Delete old private chat room
        for room in private_rooms:
            for user in room.allowed.all():
                if not user.is_active:
                    room.archived = True
                    room.save()
                    try:
                        last_message = Message.objects.filter(room_id=room.id).latest('time')
                    except (Message.DoesNotExist):
                        # TODO This happens only for rooms without messages so not really needed
                        # logger.info(f'Message.DoesNotExist2 in {room}')
                        continue
                    if last_message.time < (timezone.now() - td(days=get_param('delete_inactive_user_after'))):  # delete inactive users private room
                        log.info(f'Chat room {room.title} deleted.')
                        room.delete()  # delete
                elif user.is_active:
                    room.archived = False
                    room.save()
