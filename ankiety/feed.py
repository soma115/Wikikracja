from django.db.models import Q
from django.utils import timezone

from core.richtext import plain_text

from .models import Survey


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return surveys created or modified since the previous feed period."""
    surveys = Survey.objects.filter(Q(created_at__gte=since) | Q(updated_at__gte=since)).select_related('author', 'author__uzytkownik').order_by('-updated_at')
    items = []
    for survey in surveys:
        items.append(
            {
                'content_type': 'survey',
                'title': survey.title,
                'description': plain_text(survey.description or '', 125),
                'author': survey.author,
                'timestamp': survey.updated_at,
                'url': f"/ankiety/{survey.pk}/",
                'object_id': survey.pk,
            }
        )
    return items
