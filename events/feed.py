from datetime import timedelta as td

from django.utils import timezone

from core.feed_registry import DIGEST_GROUP_ID
from core.richtext import plain_text

from .models import Event


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return recently changed events and upcoming event occurrences."""
    items = []
    changed_events = Event.objects.filter(updated_at__gte=since).order_by('-updated_at')
    for event in changed_events:
        items.append(
            {
                'content_type': 'event',
                'title': event.title,
                'description': plain_text(event.description or '', 125),
                'author': None,
                'timestamp': event.updated_at,
                'url': f"/events/{event.pk}/",
                'object_id': event.pk,
                'activity_kind': 'change',
                DIGEST_GROUP_ID: f'change:{event.pk}',
            }
        )

    events = Event.objects.filter(is_active=True).select_related()
    upcoming_events = []
    for event in events:
        next_occurrence = event.get_next_occurrence()
        if next_occurrence and next_occurrence >= timezone.now() - td(days=1):
            upcoming_events.append((event, next_occurrence))
    upcoming_events.sort(key=lambda item: item[1])

    for event, next_occurrence in upcoming_events:
        items.append(
            {
                'content_type': 'event',
                'title': event.title,
                'description': plain_text(event.description or '', 125),
                'author': None,
                'timestamp': next_occurrence,
                'url': f"/events/{event.pk}/",
                'object_id': event.pk,
                'activity_kind': 'upcoming',
            }
        )
    return items
