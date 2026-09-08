from django.utils import timezone

from core.richtext import plain_text

from .models import Survey


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for surveys created since `since`."""
    surveys = Survey.objects.filter(created_at__gte=since).select_related("author", "author__uzytkownik").order_by("-created_at")
    items = []
    for survey in surveys:
        items.append(
            {
                "content_type": "survey",
                "title": survey.title,
                "description": plain_text(survey.description or '', 125),
                "author": survey.author,
                "timestamp": survey.created_at,
                "url": f"/ankiety/{survey.pk}/",
                "object_id": survey.pk,
            }
        )
    return items
