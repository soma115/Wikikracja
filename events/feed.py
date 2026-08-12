from datetime import timedelta as td

from django.utils import timezone
from django.utils.html import strip_tags

from .models import Event


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for upcoming event occurrences.

    `since` is not used as a hard filter because recurring events are expanded
    from `now`; only occurrences in the last day or future are included.
    """
    events = Event.objects.filter(is_active=True).select_related()
    upcoming_events = []
    for event in events:
        next_occurrence = event.get_next_occurrence()
        if next_occurrence and next_occurrence >= timezone.now() - td(days=1):
            upcoming_events.append((event, next_occurrence))
    upcoming_events.sort(key=lambda x: x[1])

    items = []
    for event, next_occurrence in upcoming_events:
        clean_description = strip_tags(event.description) if event.description else ''
        items.append(
            {
                'content_type': 'event',
                'title': event.title,
                'description': clean_description[:125] + '...' if clean_description and len(clean_description) > 125 else clean_description,
                'author': None,
                'timestamp': next_occurrence,
                'url': f"/events/{event.pk}/",
                'object_id': event.pk,
            }
        )
    return items
