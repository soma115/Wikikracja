from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import pgettext_lazy

from home.colors import category_color

from .models import Task


def search(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return search results for tasks."""
    if 'task' not in active_cats:
        return []

    tasks = Task.objects.filter(Q(title__icontains=query) | Q(description__icontains=query)).distinct()[:limit]

    return [
        {'cat': 'task', 'type': pgettext_lazy('task', 'Activity'), 'type_color': category_color('task'), 'title': obj.title, 'description': (strip_tags(obj.description) or '')[:120], 'url': f'/tasks/{obj.pk}/'}
        for obj in tasks
    ]
