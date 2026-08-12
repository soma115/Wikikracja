from django.utils import timezone
from django.utils.html import strip_tags

from .models import Survey


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for surveys created since `since`."""
    surveys = Survey.objects.filter(created_at__gte=since).select_related("author", "author__uzytkownik").order_by("-created_at")
    items = []
    for survey in surveys:
        clean_description = strip_tags(survey.description) if survey.description else ""
        description = clean_description[:125] + "..." if clean_description and len(clean_description) > 125 else clean_description
        items.append(
            {"content_type": "survey", "title": survey.title, "description": description, "author": survey.author, "timestamp": survey.created_at, "url": f"/ankiety/{survey.pk}/", "object_id": survey.pk}
        )
    return items
