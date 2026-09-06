from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from core.colors import category_color

from .models import Argument as DecyzjaArgument
from .models import Decyzja


def search(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return search results for decisions (votings) and their arguments."""
    if 'decision' not in active_cats:
        return []

    results = []

    decisions = Decyzja.objects.filter(Q(title__icontains=query) | Q(tresc__icontains=query) | Q(uzasadnienie__icontains=query) | Q(args_for__icontains=query) | Q(args_against__icontains=query)).distinct()[
        :limit
    ]

    q_low = query.lower()
    for obj in decisions:
        matched_field = ''
        if q_low in (obj.args_for or '').lower():
            matched_field = str(_('argument for'))
        elif q_low in (obj.args_against or '').lower():
            matched_field = str(_('argument against'))
        elif q_low in (obj.uzasadnienie or '').lower():
            matched_field = str(_('Reasoning'))

        snippet = strip_tags(obj.tresc or obj.uzasadnienie or '') or ''
        results.append(
            {
                'cat': 'decision',
                'type': _('Voting'),
                'type_color': category_color('decision'),
                'title': obj.title,
                'description': snippet[:120],
                'meta': (obj.get_status_display() + (f' · {matched_field}' if matched_field else '')),
                'url': f'/glosowania/details/{obj.pk}/',
            }
        )

    arguments_qs = DecyzjaArgument.objects.filter(content__icontains=query).select_related('decyzja', 'author').distinct()[: limit + 5]

    for arg in arguments_qs:
        arg_type_label = str(_('argument for')) if arg.argument_type == 'FOR' else str(_('argument against'))
        status_label = arg.decyzja.get_status_display()
        author_name = arg.author.username if arg.author else str(_('Unknown'))
        results.append(
            {
                'cat': 'decision',
                'type': _('Voting'),
                'type_color': category_color('decision'),
                'title': arg.decyzja.title,
                'description': arg.content[:120],
                'meta': f'{status_label} · {arg_type_label} · {author_name}',
                'url': f'/glosowania/details/{arg.decyzja.pk}/',
            }
        )

    return results
