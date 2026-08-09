from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import CitizenActivity


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for citizen activities created since `since`."""
    activities = CitizenActivity.objects.filter(timestamp__gte=since).select_related('uzytkownik', 'uzytkownik__uid').order_by('-timestamp')
    items = []
    for activity in activities:
        items.append(
            {
                'content_type': 'citizen',
                'title': activity.get_activity_type_display(),
                'description': f"{activity.uzytkownik.uid.username} - {_(activity.description)}",
                'author': activity.uzytkownik.uid,
                'timestamp': activity.timestamp,
                'url': f"/obywatele/{activity.uzytkownik.uid.id}/",
                'object_id': activity.pk,
            }
        )
    return items


def mark_as_read(object_id: int, user) -> None:
    from home.models import ReadStatus

    ReadStatus.objects.get_or_create(user=user, content_type=ReadStatus.ContentType.CITIZEN, object_id=object_id)


def mark_as_unread(object_id: int, user) -> None:
    from home.models import ReadStatus

    ReadStatus.objects.filter(user=user, content_type=ReadStatus.ContentType.CITIZEN, object_id=object_id).delete()
