from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from chat.signals import request_discussion_room

from .models import Survey


@receiver(post_save, sender=Survey)
def create_or_update_survey_chat_room(sender, instance, created, **kwargs):
    """Ask the chat app to create or update a discussion room for the survey."""
    if not created and not instance.chat_room_id:
        return

    allowed_users = User.objects.filter(is_active=True) if created else None
    request_discussion_room(instance, founder=instance.author, allowed_users=allowed_users)
