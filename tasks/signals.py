import logging

from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from chat.signals import chat_room_requested
from core.services.feed import invalidate_feed_cache_on_change
from core.signals import task_created
from core.utils import build_site_url

from .models import Task

log = logging.getLogger(__name__)


@receiver(post_save, sender=Task)
def create_task_chat_room(sender, instance, created, **kwargs):
    """Ask the chat app to create a discussion room for this task."""
    if not created:
        return

    room_title = instance.get_chat_room_title()

    task_path = reverse('tasks:detail', kwargs={'pk': instance.pk})
    task_url = build_site_url(task_path)
    message_text = _("Discussion room for activity: <a href='%(task_url)s'>%(task_title)s</a>") % {'task_title': instance.title, 'task_url': task_url}

    chat_room_requested.send(
        sender=Task,
        instance=instance,
        title=room_title,
        founder=instance.created_by,
        allowed_users=User.objects.filter(is_active=True),
        welcome_message=message_text,
        welcome_message_sender=instance.created_by,
        welcome_message_anonymous=False,
        source_app='tasks',
        source_object_id=instance.pk,
    )

    task_created.send(sender=Task, task=instance, url=task_url)

    log.info(f"Chat room '{room_title}' requested for task #{instance.id}")


@receiver(pre_delete, sender=Task)
def delete_task_chat_room(sender, instance, **kwargs):
    """
    Automatically delete the associated chat room when a task is deleted
    """
    room = instance.chat_room
    if room:
        room.delete()
        log.info(f"Deleted chat room '{room}' for task #{instance.id}")
    else:
        log.info(f"No chat room linked to task #{instance.id}, nothing to delete")


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def _invalidate_feed_cache_on_task_change(sender, **kwargs):
    invalidate_feed_cache_on_change(sender, **kwargs)
