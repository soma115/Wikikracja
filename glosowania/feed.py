from django.utils import timezone

from core.richtext import plain_text

from .models import Decyzja


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for decisions modified since `since`."""
    decisions = Decyzja.objects.filter(data_ostatniej_modyfikacji__gte=since).select_related('author', 'author__uzytkownik').order_by('-data_ostatniej_modyfikacji')
    items = []
    for decision in decisions:
        items.append(
            {
                'content_type': 'decision',
                'title': decision.title,
                'description': plain_text(decision.tresc or '', 125),
                'author': decision.author,
                'status_label': decision.get_status_display(),
                'status_color': {
                    Decyzja.Status.PROPOSITION: 'primary',
                    Decyzja.Status.DISCUSSION: 'info',
                    Decyzja.Status.REFERENDUM: 'warning',
                    Decyzja.Status.REJECTED: 'danger',
                    Decyzja.Status.APPROVED: 'success',
                }.get(decision.status, 'secondary'),
                'timestamp': decision.data_ostatniej_modyfikacji,
                'url': f"/glosowania/details/{decision.pk}/",
                'object_id': decision.pk,
            }
        )
    return items
