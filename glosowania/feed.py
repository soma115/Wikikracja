from django.utils import timezone
from django.utils.html import strip_tags

from .models import Decyzja


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for decisions modified since `since`."""
    decisions = Decyzja.objects.filter(data_ostatniej_modyfikacji__gte=since).select_related('author', 'author__uzytkownik').order_by('-data_ostatniej_modyfikacji')
    items = []
    for decision in decisions:
        clean_tresc = strip_tags(decision.tresc) if decision.tresc else ''
        items.append(
            {
                'content_type': 'decision',
                'title': decision.title,
                'description': clean_tresc[:125] + '...' if clean_tresc and len(clean_tresc) > 125 else clean_tresc,
                'author': decision.author,
                'timestamp': decision.data_ostatniej_modyfikacji,
                'url': f"/glosowania/details/{decision.pk}/",
                'object_id': decision.pk,
            }
        )
    return items
