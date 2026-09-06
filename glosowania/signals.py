import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext as _

from chat.signals import chat_room_requested
from core.services.feed import invalidate_feed_cache_on_change
from core.utils import get_site_domain
from glosowania.models import Decyzja

log = logging.getLogger(__name__)


@receiver(post_save, sender=Decyzja)
def create_or_update_chat_room_for_referendum(sender, instance, created, **kwargs):
    """
    Ask the chat app to create or update a discussion room for this proposal.
    """
    # Only create room when a new Decyzja is created
    if created and instance.status == Decyzja.Status.PROPOSITION:
        room_title = instance.get_chat_room_title()

        HOST = get_site_domain()
        protocol = getattr(settings, 'SITE_PROTOCOL', 'http')
        details_url = f"{protocol}://{HOST}/glosowania/details/{instance.pk}"
        welcome_message = _("This chat room has been created for project #{id} <a href='{details_url}'>{title}</a>.\nDiscuss the proposal, share your thoughts, and ask questions here.").format(
            id=instance.pk, title=instance.title, details_url=details_url
        )

        chat_room_requested.send(
            sender=Decyzja,
            instance=instance,
            title=room_title,
            founder=instance.author,
            allowed_users=User.objects.filter(is_active=True),
            welcome_message=welcome_message,
            source_app='glosowania',
            source_object_id=instance.pk,
        )

        log.info(f'Chat room "{room_title}" requested for referendum #{instance.pk}')
    elif instance.chat_room_id:
        # Request a title update if the project title changed.
        chat_room_requested.send(
            sender=Decyzja, instance=instance, title=instance.get_chat_room_title(), founder=instance.author, allowed_users=None, welcome_message='', source_app='glosowania', source_object_id=instance.pk
        )


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


@receiver(post_save, sender=Decyzja)
@receiver(post_delete, sender=Decyzja)
def _invalidate_feed_cache_on_decyzja_change(sender, **kwargs):
    invalidate_feed_cache_on_change(sender, **kwargs)
