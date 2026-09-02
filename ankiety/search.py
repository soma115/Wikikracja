from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from home.colors import category_color

from .models import Survey


def search(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return search results for surveys."""
    if 'survey' not in active_cats:
        return []

    surveys = Survey.objects.filter(Q(title__icontains=query) | Q(description__icontains=query)).distinct()[:limit]

    return [
        {'cat': 'survey', 'type': _('Ankiety'), 'type_color': category_color('survey'), 'title': obj.title, 'description': (strip_tags(obj.description) or '')[:120], 'url': f'/ankiety/{obj.pk}/'}
        for obj in surveys
    ]
