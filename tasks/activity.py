from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from .models import Task, TaskEvaluation, TaskVote


def get_user_tasks(user):
    return Task.objects.filter(Q(created_by=user) | Q(assigned_to=user)).distinct().order_by('-created_at')


def get_user_created_items(user) -> list[dict]:
    items = []
    for task in Task.objects.filter(created_by=user).order_by('-created_at'):
        items.append({'title': task.title, 'ts': task.created_at, 'label': pgettext_lazy('task', 'Activity'), 'url': reverse('tasks:detail', kwargs={'pk': task.pk})})
    return items


def get_user_activity(user) -> list[dict]:
    items = [{'type': 'task_created', **item, 'label': _('Created activity')} for item in get_user_created_items(user)]

    for task in Task.objects.filter(assigned_to=user).order_by('-updated_at'):
        items.append({'type': 'task_assigned', 'title': task.title, 'ts': task.updated_at, 'label': _('Assigned activity'), 'url': reverse('tasks:detail', kwargs={'pk': task.pk})})

    for vote in TaskVote.objects.filter(user=user).select_related('task').order_by('-updated_at'):
        items.append({'type': 'task_vote', 'title': vote.task.title, 'ts': vote.updated_at, 'label': _('Voted on activity'), 'url': reverse('tasks:detail', kwargs={'pk': vote.task_id})})

    for evaluation in TaskEvaluation.objects.filter(user=user).select_related('task').order_by('-updated_at'):
        items.append({'type': 'task_eval', 'title': evaluation.task.title, 'ts': evaluation.updated_at, 'label': _('Evaluated activity'), 'url': reverse('tasks:detail', kwargs={'pk': evaluation.task_id})})

    return items
