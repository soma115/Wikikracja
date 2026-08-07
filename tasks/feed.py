from django.utils import timezone
from django.utils.html import strip_tags

from .models import Task


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for tasks modified since `since`."""
    tasks = Task.objects.filter(updated_at__gte=since).select_related('created_by', 'assigned_to').order_by('-updated_at')
    items = []
    for task in tasks:
        clean_description = strip_tags(task.description)
        items.append({
            'content_type': 'task',
            'title': task.title,
            'description': clean_description[:125] + '...' if len(clean_description) > 125 else clean_description,
            'author': task.created_by or task.assigned_to,
            'timestamp': task.updated_at,
            'url': f"/tasks/{task.pk}/",
            'object_id': task.pk,
        })
    return items


def mark_as_read(object_id: int, user) -> None:
    from home.models import ReadStatus
    ReadStatus.objects.get_or_create(
        user=user,
        content_type=ReadStatus.ContentType.TASK,
        object_id=object_id,
    )


def mark_as_unread(object_id: int, user) -> None:
    from home.models import ReadStatus
    ReadStatus.objects.filter(
        user=user,
        content_type=ReadStatus.ContentType.TASK,
        object_id=object_id,
    ).delete()
