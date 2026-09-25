from django.db.models import Q
from django.utils import timezone

from core.richtext import plain_text

from .activity import get_task_status_label
from .models import Task


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for tasks modified since `since` or active assigned tasks.

    Active tasks assigned to a citizen are always shown so users can track
    their own open tasks even if they have not been modified recently.
    """
    tasks = (
        Task.objects.with_metrics()
        .filter(Q(updated_at__gte=since) | Q(assigned_to__isnull=False, status=Task.Status.ACTIVE))
        .select_related('created_by', 'created_by__uzytkownik', 'assigned_to', 'assigned_to__uzytkownik', 'category')
        .order_by('-updated_at')
    )
    items = []
    for task in tasks:
        items.append(
            {
                'content_type': 'task',
                'title': task.title,
                'description': plain_text(task.description, 125),
                'author': task.created_by or task.assigned_to,
                'status_label': get_task_status_label(task),
                'status_color': {Task.Status.ACTIVE: 'warning', Task.Status.COMPLETED: 'success', Task.Status.CANCELLED: 'secondary', Task.Status.REJECTED: 'danger'}.get(task.status, 'secondary'),
                'category_label': task.category.name if task.category else None,
                'timestamp': task.updated_at,
                'url': f"/tasks/{task.pk}/",
                'object_id': task.pk,
            }
        )
    return items
