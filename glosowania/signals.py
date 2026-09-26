from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import override

from chat.signals import request_discussion_room
from core.utils import build_site_url
from glosowania.models import Decyzja


@receiver(post_save, sender=Decyzja)
def create_or_update_chat_room_for_referendum(sender, instance, created, **kwargs):
    """
    Ask the chat app to create or update a discussion room for this proposal.
    """
    if created and instance.status == Decyzja.Status.PROPOSITION:
        details_url = build_site_url(reverse('glosowania:details', kwargs={'pk': instance.pk}))
        with override(settings.LANGUAGE_CODE):
            welcome_message = _("This chat room has been created for project #{id} <a href='{details_url}'>{title}</a>.\nDiscuss the proposal, share your thoughts, and ask questions here.").format(
                id=instance.pk, title=instance.title, details_url=details_url
            )
        request_discussion_room(instance, founder=instance.author, allowed_users=User.objects.filter(is_active=True), welcome_message=welcome_message)
    elif instance.chat_room_id:
        # Request a title update if the project title changed.
        request_discussion_room(instance, founder=instance.author)
