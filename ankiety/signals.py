from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext as _
from django.utils.translation import override

from chat.signals import request_discussion_room
from core.utils import build_site_url

from .models import Survey


@receiver(post_save, sender=Survey)
def create_or_update_survey_chat_room(sender, instance, created, **kwargs):
    """Ask the chat app to create or update a discussion room for the survey."""
    if not created and not instance.chat_room_id:
        return

    welcome_message = ""
    allowed_users = None
    welcome_message_sender = None
    welcome_message_anonymous = True

    if created:
        survey_url = build_site_url(instance.get_absolute_url())
        with override(settings.LANGUAGE_CODE):
            welcome_message = _("Discussion room for survey: <a href='%(survey_url)s'>%(survey_title)s</a>") % {"survey_title": instance.title, "survey_url": survey_url}
        allowed_users = User.objects.filter(is_active=True)
        welcome_message_sender = instance.author
        welcome_message_anonymous = False

    request_discussion_room(
        instance, founder=instance.author, allowed_users=allowed_users, welcome_message=welcome_message, welcome_message_sender=welcome_message_sender, welcome_message_anonymous=welcome_message_anonymous
    )
