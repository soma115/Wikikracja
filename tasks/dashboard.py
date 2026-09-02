from django.db.models import Q

from .models import Task


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for tasks."""
    my_tasks = Task.objects.filter(assigned_to=user, status=Task.Status.ACTIVE).order_by('updated_at')[:3]

    my_tasks_count = Task.objects.filter(Q(assigned_to=user) | Q(votes__user=user, votes__value=1), status=Task.Status.ACTIVE).distinct().count()

    return {'my_tasks': my_tasks, 'my_tasks_count': my_tasks_count}
