from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from chat.signals import request_discussion_room
from core.signals import task_created, task_helper_joined, task_status_changed
from core.utils import build_site_url

from .models import Task, TaskVote


@receiver(pre_save, sender=Task)
def remember_task_status(sender, instance, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'status' not in update_fields:
        instance._previous_status = None
    else:
        instance._previous_status = Task.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None


@receiver(post_save, sender=Task)
def notify_task_status_changed(sender, instance, created, **kwargs):
    previous_status = getattr(instance, '_previous_status', None)
    if not created and previous_status is not None and previous_status != instance.status:
        transaction.on_commit(lambda: task_status_changed.send(sender=Task, task=instance, previous_status=previous_status))


@receiver(pre_save, sender=TaskVote)
def remember_task_vote(sender, instance, **kwargs):
    instance._previous_value = TaskVote.objects.filter(pk=instance.pk).values_list('value', flat=True).first() if instance.pk else None


@receiver(post_save, sender=TaskVote)
def notify_task_helper_joined(sender, instance, created, **kwargs):
    previous_value = getattr(instance, '_previous_value', None)
    if instance.value != TaskVote.Value.UP or (not created and previous_value == TaskVote.Value.UP):
        return

    task = Task.objects.select_related('assigned_to').filter(pk=instance.task_id).first()
    if not task or not task.assigned_to_id or task.assigned_to_id == instance.user_id:
        return

    transaction.on_commit(lambda: task_helper_joined.send(sender=TaskVote, task=task, helper=instance.user, coordinator_id=task.assigned_to_id))


@receiver(post_save, sender=Task)
def create_task_chat_room(sender, instance, created, **kwargs):
    """Ask the chat app to create a discussion room for this task."""
    if not created:
        return

    task_url = build_site_url(reverse('tasks:detail', kwargs={'pk': instance.pk}))
    request_discussion_room(instance, founder=instance.created_by, allowed_users=User.objects.filter(is_active=True))

    transaction.on_commit(lambda: task_created.send(sender=Task, task=instance, url=task_url))
