from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

from ankiety.models import Survey
from board.models import Post
from chat.models import Message, Room
from events.models import Event
from glosowania.models import Argument as DecyzjaArgument
from glosowania.models import Decyzja
from tasks.models import Task

from ..colors import category_color


def run_global_search(query: str, active_cats: set, user) -> list:
    """Return a list of search result dicts across the selected categories."""
    if not query:
        return []

    results = []

    # ── Board posts ──────────────────────────────────────────────
    if 'post' in active_cats:
        posts = Post.objects.filter(Q(title__icontains=query) | Q(subtitle__icontains=query) | Q(text__icontains=query)).distinct()[:10]
        for obj in posts:
            results.append({'cat': 'post', 'type': _('Post'), 'type_color': category_color('post'), 'title': obj.title, 'description': (strip_tags(obj.text) or '')[:120], 'url': f'/board/view/{obj.pk}/'})

    # ── Tasks ────────────────────────────────────────────────────
    if 'task' in active_cats:
        tasks = Task.objects.filter(Q(title__icontains=query) | Q(description__icontains=query)).distinct()[:10]
        for obj in tasks:
            results.append({'cat': 'task', 'type': _('Task'), 'type_color': category_color('task'), 'title': obj.title, 'description': (strip_tags(obj.description) or '')[:120], 'url': f'/tasks/{obj.pk}/'})

    # ── Voting / decisions – all statuses ──
    if 'decision' in active_cats:
        # 1. Search main decision fields
        decisions = Decyzja.objects.filter(Q(title__icontains=query) | Q(tresc__icontains=query) | Q(uzasadnienie__icontains=query) | Q(args_for__icontains=query) | Q(args_against__icontains=query)).distinct()[
            :10
        ]

        for obj in decisions:
            matched_field = ''
            q_low = query.lower()
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

        # 2. Search Argument model (user-added arguments across all statuses)
        arguments_qs = DecyzjaArgument.objects.filter(content__icontains=query).select_related('decyzja', 'author').distinct()[:15]

        for arg in arguments_qs:
            arg_type_label = str(_('argument for')) if arg.argument_type == 'FOR' else str(_('argument against'))
            status_label = arg.decyzja.get_status_display()
            url = f'/glosowania/details/{arg.decyzja.pk}/'
            author_name = arg.author.username if arg.author else str(_('Unknown'))
            results.append(
                {
                    'cat': 'decision',
                    'type': _('Voting'),
                    'type_color': category_color('decision'),
                    'title': arg.decyzja.title,
                    'description': arg.content[:120],
                    'meta': f'{status_label} · {arg_type_label} · {author_name}',
                    'url': url,
                }
            )

    # ── Surveys ──────────────────────────────────────────────────
    if 'survey' in active_cats:
        surveys = Survey.objects.filter(Q(title__icontains=query) | Q(description__icontains=query)).distinct()[:10]
        for obj in surveys:
            results.append(
                {'cat': 'survey', 'type': _('Ankiety'), 'type_color': category_color('survey'), 'title': obj.title, 'description': (strip_tags(obj.description) or '')[:120], 'url': f'/ankiety/{obj.pk}/'}
            )

    # ── Events ───────────────────────────────────────────────────
    if 'event' in active_cats:
        events = Event.objects.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(place__icontains=query)).distinct()[:10]
        for obj in events:
            results.append({'cat': 'event', 'type': _('Event'), 'type_color': category_color('event'), 'title': obj.title, 'description': (strip_tags(obj.description) or '')[:120], 'url': f'/events/{obj.pk}/'})

    # ── Citizens ─────────────────────────────────────────────────
    if 'citizen' in active_cats:
        users = User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)).distinct()[:10]
        for obj in users:
            results.append(
                {'cat': 'citizen', 'type': _('Citizen'), 'type_color': category_color('citizen'), 'title': obj.get_full_name() or obj.username, 'description': f'@{obj.username}', 'url': f'/obywatele/{obj.pk}/'}
            )

    # ── Chat (rooms + messages user has access to) ────────────────
    if 'chat' in active_cats:
        accessible_rooms = Room.objects.filter(allowed=user)

        # Rooms by title
        rooms = accessible_rooms.filter(title__icontains=query).distinct()[:5]
        for obj in rooms:
            results.append({'cat': 'chat', 'type': _('Chat'), 'type_color': category_color('chat'), 'title': obj.displayed_name(user), 'description': '', 'url': f'/chat/#room_id={obj.pk}'})

        # Messages in accessible rooms
        messages_qs = Message.objects.filter(Q(text__icontains=query), room__in=accessible_rooms).select_related('sender', 'room').order_by('-time').distinct()[:15]
        for obj in messages_qs:
            sender_name = str(_('System')) if obj.sender is None else (str(_('Anonymous')) if obj.anonymous else obj.sender.username)
            results.append(
                {
                    'cat': 'chat',
                    'type': _('Chat message'),
                    'type_color': category_color('chat'),
                    'title': obj.room.displayed_name(user),
                    'description': f'{sender_name}: {strip_tags(obj.text)[:100]}',
                    'url': f'/chat/#room_id={obj.room.pk}',
                }
            )

    return results
