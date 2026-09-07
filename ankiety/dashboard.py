from django.utils import timezone

from .models import Survey


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widget for active surveys."""
    now = timezone.now()
    active_surveys = Survey.objects.filter(end_date__gte=now).select_related('author').order_by('-created_at')[:5]
    return {'active_surveys': active_surveys}
