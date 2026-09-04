from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from django.apps import apps
from django.db.models import Q
from django.urls import Resolver404, resolve

MAX_LINKS = 50
MAX_URL_LENGTH = 2048


@dataclass(frozen=True)
class LinkRoute:
    app_label: str
    model_name: str
    lookup: str
    title: str
    login_required: bool = True
    public_field: str = ''


ROUTES = {
    'tasks:detail': LinkRoute('tasks', 'Task', 'pk', 'title'),
    'glosowania:details': LinkRoute('glosowania', 'Decyzja', 'pk', 'title'),
    'ankiety:detail': LinkRoute('ankiety', 'Survey', 'pk', 'title'),
    'events:detail': LinkRoute('events', 'Event', 'pk', 'title', login_required=False, public_field='is_public'),
    'obywatele:obywatele_szczegoly': LinkRoute('auth', 'User', 'pk', 'user'),
    'obywatele:poczekalnia_szczegoly': LinkRoute('auth', 'User', 'pk', 'user'),
    'board:view_post': LinkRoute('board', 'Post', 'pk', 'title', login_required=False, public_field='is_public'),
    'board:view_post_by_slug': LinkRoute('board', 'Post', 'slug', 'title', login_required=False, public_field='is_public'),
    'board_post_by_slug': LinkRoute('board', 'Post', 'slug', 'title', login_required=False, public_field='is_public'),
}


def _local_url(url, host):
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme and parsed.scheme not in ('http', 'https'):
        return None
    if parsed.netloc and parsed.netloc.casefold() != host.casefold():
        return None
    if not parsed.path.startswith('/'):
        return None
    return parsed


def _resolve_path(path):
    try:
        return resolve(path)
    except Resolver404:
        if path != '/' and not path.endswith('/'):
            try:
                return resolve(f'{path}/')
            except Resolver404:
                pass
    return None


def _object_title(obj, title):
    if title == 'user':
        return obj.get_full_name() or obj.get_username()
    return getattr(obj, title)


def resolve_link_titles(urls, request):
    originals = list(dict.fromkeys(url for url in urls if isinstance(url, str)))[:MAX_LINKS]
    grouped = defaultdict(list)
    room_links = []

    for original in originals:
        parsed = _local_url(original, request.get_host())
        if parsed is None:
            continue

        if parsed.path.rstrip('/') == '/chat':
            room_id = parse_qs(parsed.fragment).get('room_id', [None])[0]
            try:
                room_links.append((original, int(room_id)))
            except (TypeError, ValueError):
                pass
            continue

        match = _resolve_path(parsed.path)
        route = ROUTES.get(match.view_name) if match else None
        if route is None or (route.login_required and not request.user.is_authenticated):
            continue
        value = match.kwargs.get(route.lookup)
        if value is not None:
            grouped[route].append((original, value))

    titles = {}
    for route, links in grouped.items():
        model = apps.get_model(route.app_label, route.model_name)
        values = {value for _, value in links}
        queryset = model.objects.filter(**{f'{route.lookup}__in': values})
        if route.public_field and not request.user.is_authenticated:
            queryset = queryset.filter(**{route.public_field: True})
        objects = {str(getattr(obj, route.lookup)): obj for obj in queryset}
        for original, value in links:
            obj = objects.get(str(value))
            if obj is not None:
                titles[original] = str(_object_title(obj, route.title))

    if room_links and request.user.is_authenticated:
        room_model = apps.get_model('chat', 'Room')
        room_ids = {room_id for _, room_id in room_links}
        rooms = {room.pk: room for room in room_model.objects.filter(Q(public=True) | Q(allowed=request.user), pk__in=room_ids).distinct().prefetch_related('allowed')}
        for original, room_id in room_links:
            room = rooms.get(room_id)
            if room is not None:
                titles[original] = room.displayed_name(request.user)

    return titles
