import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext as _

from chat.models import Message, Room
from glosowania.models import Decyzja
from zzz.utils import get_site_domain

log = logging.getLogger(__name__)


@receiver(post_save, sender=Decyzja)
def create_or_update_chat_room_for_referendum(sender, instance, created, **kwargs):
    """
    Create a public chat room for each new project (Decyzja) when it is created
    and update room title when project title changes.
    """
    # Only create room when a new Decyzja is created
    if created and instance.status == Decyzja.Status.PROPOSITION:
        # Create room title based on project ID and title
        # Use English prefix (not translated) for consistency in room categorization
        room_title = instance.get_chat_room_title()

        # Create new chat room
        try:
            # Create new public chat room for voting
            room = Room.objects.create(title=room_title, public=True, archived=False, protected=True, founder=instance.author)

            # Add all active users to the room
            active_users = User.objects.filter(is_active=True)
            room.allowed.set(active_users)

            # Link room to Decyzja instance
            instance.chat_room = room
            instance.save(update_fields=['chat_room'])

            # Create initial welcome message in the room
            HOST = get_site_domain()
            protocol = getattr(settings, 'SITE_PROTOCOL', 'http')
            details_url = f"{protocol}://{HOST}/glosowania/details/{instance.pk}"
            welcome_message = _("This chat room has been created for project #{id} \"{title}\".\nView details: {details_url}\nDiscuss the proposal, share your thoughts, and ask questions here.").format(id=instance.pk, title=instance.title, details_url=details_url)

            Message.objects.create(room=room, text=welcome_message, anonymous=True, sender=None)

            log.info(f'Chat room "{room_title}" created for referendum #{instance.pk}')
        except Exception as e:
            log.error(f'Failed to create chat room for referendum #{instance.pk}: {str(e)}')
    else:
        # Update room title if project title changed
        if instance.chat_room:
            new_title = instance.get_chat_room_title()
            if instance.chat_room.title != new_title:
                instance.chat_room.title = new_title
                instance.chat_room.save(update_fields=['title'])
                log.info(f"Updated chat room title to '{new_title}' for referendum #{instance.pk}")


@receiver(pre_delete, sender=Decyzja)
def delete_decyzja_chat_room(sender, instance, **kwargs):
    """
    Automatically delete the associated chat room when a Decyzja (voting) is deleted.
    Note: Currently, Decyzja objects are not deleted in the system, but this signal
    is here for future-proofing in case deletion functionality is added.
    """
    room = instance.chat_room
    if room:
        room.delete()
        log.info(f"Deleted chat room '{room.title}' for referendum #{instance.pk}")
    else:
        log.info(f"No chat room linked to referendum #{instance.pk}, nothing to delete")
