from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.richtext import plain_text

from .activity import get_task_status_label
from .models import Task, TaskVote

_STATUS_COLORS = {Task.Status.ACTIVE: 'warning', Task.Status.COMPLETED: 'success', Task.Status.CANCELLED: 'secondary', Task.Status.REJECTED: 'danger'}


def _task_feed_item(task, *, timestamp, description, author, activity_kind, vote_id=None):
    item = {
        'content_type': 'task',
        'title': task.title,
        'description': description,
        'author': author,
        'status_label': get_task_status_label(task),
        'status_color': _STATUS_COLORS.get(task.status, 'secondary'),
        'category_label': task.category.name if task.category else None,
        'timestamp': timestamp,
        'url': f"/tasks/{task.pk}/",
        'object_id': task.pk,
        'activity_kind': activity_kind,
    }
    if vote_id is not None:
        item['vote_id'] = vote_id
    return item


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return task changes and recent votes that express interest in an activity."""
    tasks = (
        Task.objects.with_metrics()
        .filter(Q(updated_at__gte=since) | Q(assigned_to__isnull=False, status=Task.Status.ACTIVE))
        .select_related('created_by', 'created_by__uzytkownik', 'assigned_to', 'assigned_to__uzytkownik', 'category')
        .order_by('-updated_at')
    )
    items = [_task_feed_item(task, timestamp=task.updated_at, description=plain_text(task.description, 125), author=task.created_by or task.assigned_to, activity_kind='task') for task in tasks]

    votes = list(TaskVote.objects.filter(updated_at__gte=since).select_related('task', 'user').order_by('-updated_at'))
    task_ids = {vote.task_id for vote in votes}
    tasks_by_id = {task.pk: task for task in Task.objects.with_metrics().filter(pk__in=task_ids).select_related('created_by', 'created_by__uzytkownik', 'assigned_to', 'assigned_to__uzytkownik', 'category')}
    items.extend(
        _task_feed_item(
            tasks_by_id[vote.task_id],
            timestamp=vote.updated_at,
            description=_('Wants to help') if vote.value == TaskVote.Value.UP else _('Opposes activity'),
            author=vote.user,
            activity_kind='vote',
            vote_id=vote.pk,
        )
        for vote in votes
        if vote.task_id in tasks_by_id
    )
    return items
