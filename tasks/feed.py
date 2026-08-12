from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags

from .models import Task


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for tasks modified since `since` or active assigned tasks.

    Active tasks assigned to a citizen are always shown so users can track
    their own open tasks even if they have not been modified recently.
    """
    tasks = (
        Task.objects.filter(Q(updated_at__gte=since) | Q(assigned_to__isnull=False, status=Task.Status.ACTIVE))
        .select_related('created_by', 'created_by__uzytkownik', 'assigned_to', 'assigned_to__uzytkownik')
        .order_by('-updated_at')
    )
    items = []
    for task in tasks:
        clean_description = strip_tags(task.description)
        items.append(
            {
                'content_type': 'task',
                'title': task.title,
                'description': clean_description[:125] + '...' if len(clean_description) > 125 else clean_description,
                'author': task.created_by or task.assigned_to,
                'timestamp': task.updated_at,
                'url': f"/tasks/{task.pk}/",
                'object_id': task.pk,
            }
        )
    return items
