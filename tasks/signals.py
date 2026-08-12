import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from chat.models import Message, Room
from home.services.feed import invalidate_feed_cache_on_change
from zzz.utils import get_site_domain

from .models import Task, TaskVote

log = logging.getLogger(__name__)


@receiver(post_save, sender=Task)
def create_task_chat_room(sender, instance, created, **kwargs):
    """
    Automatically create a public chat room for each new task
    """
    if created:

        def _create_room():
            room_title = instance.get_chat_room_title()

            # Create new public room
            room = Room.objects.create(title=room_title, public=True, archived=False, protected=True, last_activity=timezone.now(), founder=instance.created_by)

            # Allow all active users access to the room
            active_users = User.objects.filter(is_active=True)
            room.allowed.set(active_users)

            # Link room to task via FK
            Task.objects.filter(pk=instance.pk).update(chat_room=room)

            log.info(f"Created chat room '{room_title}' for task #{instance.id}")

            # Send initial message with link back to the task
            domain = get_site_domain()
            task_path = reverse('tasks:detail', kwargs={'pk': instance.pk})
            protocol = getattr(settings, 'SITE_PROTOCOL', 'http')
            task_url = f"{protocol}://{domain}{task_path}"
            message_text = _('Discussion room for task "%(task_title)s": %(task_url)s') % {'task_title': instance.title, 'task_url': task_url}

            Message.objects.create(sender=instance.created_by, text=message_text, room=room, anonymous=False)

            log.info(f"Sent initial message to chat room '{room_title}'")

        transaction.on_commit(_create_room)


@receiver(post_save, sender=Task)
@receiver(post_delete, sender=Task)
def invalidate_task_list_on_task_change(sender, instance, **kwargs):
    from .views import invalidate_task_list_cache

    invalidate_task_list_cache()


@receiver(post_save, sender=TaskVote)
@receiver(post_delete, sender=TaskVote)
def invalidate_task_list_on_vote_change(sender, instance, **kwargs):
    from .views import invalidate_task_list_cache

    invalidate_task_list_cache(user_id=instance.user_id)


@receiver(m2m_changed, sender=Room.seen_by.through)
def invalidate_task_list_on_seen_by_change(sender, instance, action, pk_set, **kwargs):
    # instance is Room, pk_set is set of user IDs being added/removed
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    # Only invalidate users whose seen_by changed, and only if room is linked to a task
    if not hasattr(instance, 'task') or not instance.task.exists():
        return
    from .views import invalidate_task_list_cache

    if pk_set:
        for user_id in pk_set:
            invalidate_task_list_cache(user_id=user_id)
    else:
        # post_clear has no pk_set — invalidate all
        invalidate_task_list_cache()


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
