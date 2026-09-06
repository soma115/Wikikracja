from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from core.colors import category_color

from .models import Post


def search(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return search results for board posts."""
    if 'post' not in active_cats:
        return []

    posts = Post.objects.filter(Q(title__icontains=query) | Q(subtitle__icontains=query) | Q(text__icontains=query)).distinct()[:limit]

    return [{'cat': 'post', 'type': _('Post'), 'type_color': category_color('post'), 'title': obj.title, 'description': (strip_tags(obj.text) or '')[:120], 'url': f'/board/view/{obj.pk}/'} for obj in posts]
