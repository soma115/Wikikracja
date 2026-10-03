from django.utils import timezone

from core.richtext import plain_text

from .models import Argument, Decyzja

_STATUS_COLORS = {Decyzja.Status.PROPOSITION: 'primary', Decyzja.Status.DISCUSSION: 'info', Decyzja.Status.REFERENDUM: 'warning', Decyzja.Status.REJECTED: 'danger', Decyzja.Status.APPROVED: 'success'}


def _decision_feed_item(decision, *, timestamp, description, author, activity_kind, argument_id=None):
    item = {
        'content_type': 'decision',
        'title': decision.title,
        'description': description,
        'author': author,
        'status_label': decision.get_status_display(),
        'status_color': _STATUS_COLORS.get(decision.status, 'secondary'),
        'timestamp': timestamp,
        'url': f"/glosowania/details/{decision.pk}/",
        'object_id': decision.pk,
        'activity_kind': activity_kind,
    }
    if argument_id is not None:
        item['argument_id'] = argument_id
    return item


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return recently modified decisions and newly added arguments."""
    decisions = Decyzja.objects.filter(data_ostatniej_modyfikacji__gte=since).select_related('author', 'author__uzytkownik').order_by('-data_ostatniej_modyfikacji')
    arguments = Argument.objects.filter(created_at__gte=since).select_related('decyzja', 'decyzja__author', 'decyzja__author__uzytkownik', 'author').order_by('-created_at')

    items = [
        _decision_feed_item(decision, timestamp=decision.data_ostatniej_modyfikacji, description=plain_text(decision.tresc or '', 125), author=decision.author, activity_kind='decision')
        for decision in decisions
    ]
    items.extend(
        _decision_feed_item(
            argument.decyzja,
            timestamp=argument.created_at,
            description=f'{argument.get_argument_type_display()}: {plain_text(argument.content, 100)}',
            author=argument.author,
            activity_kind='argument',
            argument_id=argument.pk,
        )
        for argument in arguments
    )
    return items
