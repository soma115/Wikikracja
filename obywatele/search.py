from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.colors import category_color


def search(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return search results for citizens (users)."""
    if 'citizen' not in active_cats:
        return []

    users = User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)).distinct()[:limit]

    return [
        {'cat': 'citizen', 'type': _('Citizen'), 'type_color': category_color('citizen'), 'title': obj.get_full_name() or obj.username, 'description': f'@{obj.username}', 'url': f'/obywatele/{obj.pk}/'}
        for obj in users
    ]
