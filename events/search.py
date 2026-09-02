from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from home.colors import category_color

from .models import Event


def search(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return search results for events."""
    if 'event' not in active_cats:
        return []

    events = Event.objects.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(place__icontains=query)).distinct()[:limit]

    return [
        {'cat': 'event', 'type': _('Event'), 'type_color': category_color('event'), 'title': obj.title, 'description': (strip_tags(obj.description) or '')[:120], 'url': f'/events/{obj.pk}/'} for obj in events
    ]
