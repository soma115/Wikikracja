import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext as _

from chat.signals import chat_room_requested
from core.utils import build_site_url

from .models import Survey

log = logging.getLogger(__name__)


@receiver(post_save, sender=Survey)
def create_or_update_survey_chat_room(sender, instance, created, **kwargs):
    """Ask the chat app to create or update a discussion room for the survey."""
    if not created and not instance.chat_room_id:
        return

    room_title = instance.get_chat_room_title()
    welcome_message = ""
    allowed_users = None
    welcome_message_sender = None
    welcome_message_anonymous = True

    if created:
        survey_url = build_site_url(instance.get_absolute_url())
        welcome_message = _("Discussion room for survey: <a href='%(survey_url)s'>%(survey_title)s</a>") % {"survey_title": instance.title, "survey_url": survey_url}
        allowed_users = User.objects.filter(is_active=True)
        welcome_message_sender = instance.author
        welcome_message_anonymous = False

    chat_room_requested.send(
        sender=Survey,
        instance=instance,
        title=room_title,
        founder=instance.author,
        allowed_users=allowed_users,
        welcome_message=welcome_message,
        welcome_message_sender=welcome_message_sender,
        welcome_message_anonymous=welcome_message_anonymous,
        source_app="ankiety",
        source_object_id=instance.pk,
    )
    log.info("Chat room '%s' requested for survey #%s", room_title, instance.pk)


@receiver(pre_delete, sender=Survey)
def delete_survey_chat_room(sender, instance, **kwargs):
    """Delete the survey's discussion room together with the survey."""
    room = instance.chat_room
    if room:
        room.delete()
        log.info("Deleted chat room '%s' for survey #%s", room.title, instance.pk)
