from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from chat.signals import request_discussion_room
from glosowania.models import Decyzja


@receiver(post_save, sender=Decyzja)
def create_or_update_chat_room_for_referendum(sender, instance, created, **kwargs):
    """
    Ask the chat app to create or update a discussion room for this proposal.
    """
    if created and instance.status == Decyzja.Status.PROPOSITION:
        request_discussion_room(instance, founder=instance.author, allowed_users=User.objects.filter(is_active=True))
    elif instance.chat_room_id:
        # Request a title update if the project title changed.
        request_discussion_room(instance, founder=instance.author)
