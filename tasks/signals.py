from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import override

from chat.signals import request_discussion_room
from core.signals import task_created
from core.utils import build_site_url

from .models import Task


@receiver(post_save, sender=Task)
def create_task_chat_room(sender, instance, created, **kwargs):
    """Ask the chat app to create a discussion room for this task."""
    if not created:
        return

    task_url = build_site_url(reverse('tasks:detail', kwargs={'pk': instance.pk}))
    with override(settings.LANGUAGE_CODE):
        message_text = _("Discussion room for activity: <a href='%(task_url)s'>%(task_title)s</a>") % {'task_title': instance.title, 'task_url': task_url}

    request_discussion_room(
        instance, founder=instance.created_by, allowed_users=User.objects.filter(is_active=True), welcome_message=message_text, welcome_message_sender=instance.created_by, welcome_message_anonymous=False
    )

    task_created.send(sender=Task, task=instance, url=task_url)
