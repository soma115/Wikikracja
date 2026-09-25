from collections import defaultdict

from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from .models import Task, TaskEvaluation, TaskVote


def get_task_status_label(task):
    """Return the workflow label shown for a task outside its detail view."""
    if not task.is_active:
        return task.get_status_display()

    votes_score = getattr(task, "votes_score", 0) or 0
    if task.assigned_to_id and votes_score >= 2:
        return _("In progress")
    if votes_score >= -1 and (task.assigned_to_id is None or votes_score < 2):
        return _("Awaiting")
    return task.get_status_display()


def get_user_tasks(user):
    return Task.objects.filter(Q(created_by=user) | Q(assigned_to=user)).distinct().order_by('-created_at')


def get_active_coordinated_tasks_by_user_ids(user_ids):
    """Return active coordinated tasks grouped by coordinator ID in one query."""
    user_ids = set(user_ids)
    if not user_ids:
        return {}

    tasks_by_user = defaultdict(list)
    tasks = (
        Task.objects.with_metrics()
        .filter(assigned_to_id__in=user_ids, status=Task.Status.ACTIVE)
        .only('id', 'title', 'assigned_to_id')
        .order_by('-votes_score', '-votes_up', 'assigned_to_id', 'created_at', 'id')
    )
    for task in tasks:
        tasks_by_user[task.assigned_to_id].append(task)
    return {user_id: user_tasks[:3] for user_id, user_tasks in tasks_by_user.items()}


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
