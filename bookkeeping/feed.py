from datetime import datetime, time

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Transaction


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return financial transactions created or modified since the previous feed period."""
    transactions = Transaction.objects.filter(Q(created_date__gte=since.date()) | Q(updated_at__gte=since)).select_related('asset', 'category', 'partner', 'author')
    items = []
    for transaction in transactions:
        direction = _('Incoming') if transaction.type == Transaction.INCOMING else _('Outgoing')
        title = f'{direction}: {transaction.amount} {transaction.asset.symbol}'
        description = transaction.note or str(transaction.partner or '')
        timestamp = transaction.updated_at or timezone.make_aware(datetime.combine(transaction.created_date, time.min))
        items.append(
            {
                'content_type': 'transaction',
                'title': title,
                'description': description,
                'author': transaction.author,
                'timestamp': timestamp,
                'url': reverse('bookkeeping:transaction_detail', kwargs={'pk': transaction.pk}),
                'object_id': transaction.pk,
            }
        )
    return items
