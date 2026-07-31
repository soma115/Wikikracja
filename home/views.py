import json
import logging
import os
import re
from datetime import timedelta as td
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from board.models import Post, PostCategory
from bookkeeping.models import Asset
from bookkeeping.services import asset_balances
from chat.models import Message, Room
from chat.services import CHAT_UNREAD_CACHE_KEY, get_unread_count_for_user
from events.models import Event
from glosowania.models import Argument as DecyzjaArgument
from glosowania.models import Decyzja, KtoJuzGlosowal
from obywatele.models import CitizenActivity, Uzytkownik
from site_settings.models import SiteSettings
from site_settings.services import get_branding_version
from tasks.models import Task

from .colors import category_color
from .forms import RememberLoginForm
from .models import ReadStatus

log = logging.getLogger(__name__)

_CONTENT_TYPE_MAP = {
    'post': ReadStatus.ContentType.POST,
    'task': ReadStatus.ContentType.TASK,
    'event': ReadStatus.ContentType.EVENT,
    'message': ReadStatus.ContentType.MESSAGE,
    'room_messages': ReadStatus.ContentType.MESSAGE,
    'decision': ReadStatus.ContentType.DECISION,
    'citizen': ReadStatus.ContentType.CITIZEN,
}

FEED_CACHE_KEY = "feed_raw_v1"
FEED_CACHE_TTL = 3600


def invalidate_feed_cache():
    cache.delete(FEED_CACHE_KEY)


def build_read_status_map(user):
    return {
        content_type: set(object_ids) for content_type, object_ids in ((content_type, ReadStatus.objects.filter(user=user, content_type=content_type).values_list('object_id', flat=True)) for content_type in ReadStatus.ContentType.values)
    }


def home(request: HttpRequest):
    if not request.user.is_authenticated:
        start = Post.get_system_post('start')
        if not start:
            log.info('Add Board Message title Start.')
            start = ''
        return render(request, 'home/home.html', {
            'start': start
        })

    # Generate unified feed
    feed_items = generate_feed_items(request.user)

    # Check if we should filter to show only unread items
    # Priority: URL parameter > session (synced from localStorage)
    url_filter = request.GET.get('filter')

    if url_filter is not None:
        # URL parameter takes precedence
        filter_unread = url_filter == 'unread'
        # Update session to match URL
        request.session['show_unread_only'] = filter_unread
    elif 'show_unread_only' in request.session:
        # Use saved preference from session (synced from localStorage)
        filter_unread = request.session['show_unread_only']
    else:
        # Default: show all items
        filter_unread = False

    if filter_unread:
        feed_items = [item for item in feed_items if not item['is_read']]

    # Get counts for each section
    ongoing_count = Decyzja.objects.filter(status=Decyzja.Status.REFERENDUM).count()
    upcoming_count = Decyzja.objects.filter(status=Decyzja.Status.DISCUSSION).count()
    signatures_count = Decyzja.objects.filter(status=Decyzja.Status.PROPOSITION).count()

    # Propozycje głosowań widget (max 3, zbierające podpisy)
    new_proposals = Decyzja.objects.filter(status=Decyzja.Status.PROPOSITION).select_related('author').order_by('-data_ostatniej_modyfikacji')[:3]

    # Dyskutowane głosowania widget (max 3)
    discussed_proposals = Decyzja.objects.filter(status=Decyzja.Status.DISCUSSION).select_related('author').order_by('-data_ostatniej_modyfikacji')[:3]

    # My tasks widget (max 3, active — assigned to me or supported by me)
    my_tasks = Task.objects.filter(Q(assigned_to=request.user) | Q(votes__user=request.user, votes__value=1)).filter(status=Task.Status.ACTIVE).distinct().order_by('updated_at')[:3]

    # Active referendum widget
    active_referendum = None
    referendum_obj = Decyzja.objects.filter(status=Decyzja.Status.REFERENDUM).select_related('author').order_by('-data_referendum_start').first()
    if referendum_obj and referendum_obj.data_referendum_start and referendum_obj.data_referendum_stop:
        today = timezone.now().date()
        days_remaining = max(0, (referendum_obj.data_referendum_stop - today).days)
        total_days = max(1, (referendum_obj.data_referendum_stop - referendum_obj.data_referendum_start).days)
        time_pct = min(100, round(days_remaining / total_days * 100))
        voters_count = referendum_obj.za + referendum_obj.przeciw
        total_citizens = User.objects.filter(is_active=True).count()
        turnout_pct = round(voters_count / total_citizens * 100) if total_citizens > 0 else 0
        if time_pct > 50:
            bar_color = 'success'
        elif time_pct >= 20:
            bar_color = 'warning'
        else:
            bar_color = 'danger'
        user_voted = KtoJuzGlosowal.objects.filter(
            projekt=referendum_obj,
            ktory_uzytkownik_juz_zaglosowal=request.user,
        ).exists()
        active_referendum = {
            'obj': referendum_obj,
            'voters_count': voters_count,
            'total_citizens': total_citizens,
            'turnout_pct': turnout_pct,
            'days_remaining': days_remaining,
            'total_days': total_days,
            'time_pct': time_pct,
            'bar_color': bar_color,
            'user_voted': user_voted,
        }

    # Karta 4 — Kalendarz: 3 najbliższe wystąpienia (eventy jednorazowe i cykliczne, każde wystąpienie osobno)
    today_dt = timezone.now()
    _events_horizon_end = today_dt + td(days=90)
    _occurrences = []
    for _ev in Event.objects.filter(is_active=True):
        for _date in _ev.get_occurrences(today_dt, _events_horizon_end):
            _occurrences.append({'event': _ev, 'date': _date})
    _occurrences.sort(key=lambda o: o['date'])
    upcoming_events = _occurrences[:5]

    # Karta 5 — Finanse: salda CAŁEJ historii w walucie domyślnej (default asset).
    # Jeśli default asset nie istnieje (pusta baza assetów) → wszystkie pola = None i template
    # pokazuje onboarding CTA "dodaj aktywo". Jeśli default istnieje, ale 0 transakcji →
    # asset_balances() zwraca pustą listę → wyświetlamy 0/0/0 w symbolu defaultu.
    default_asset = Asset.get_default()
    if default_asset is None:
        default_income = default_expenses = default_balance = None
        default_symbol = None
    else:
        balances = asset_balances(asset=default_asset)
        if balances:
            row = balances[0]
            default_income, default_expenses, default_balance = row['income'], row['expenses'], row['balance']
        else:
            default_income = default_expenses = default_balance = Decimal('0')
        default_symbol = default_asset.symbol

    # Karta 6 — Nowi obywatele: 6 ostatnio dołączonych aktywnych
    new_citizens = list(Uzytkownik.objects.filter(uid__is_active=True).select_related('uid').order_by('-uid__date_joined')[:7])
    candidates_count = (Uzytkownik.objects.filter(uid__is_active=False).count() if request.user.is_staff else None)

    last_feed_items = [i for i in feed_items if i['content_type'] != 'event'][:6]

    # Unread count without events (for home page display)
    unread_items_no_events = [item for item in feed_items if not item['is_read'] and item['content_type'] != 'event']

    chat_unread_count = get_unread_count_for_user(request.user)

    # Licznik aktywnych zadań użytkownika
    my_tasks_count = Task.objects.filter(
        Q(assigned_to=request.user) | Q(votes__user=request.user, votes__value=1),
        status=Task.Status.ACTIVE,
    ).distinct().count()

    ss = SiteSettings.get()
    from site_settings.models import QuickLink

    quick_links = list(QuickLink.objects.order_by('order'))

    return render(request, 'home/home.html', {
        'feed_items': feed_items,
        'unread_items_no_events': unread_items_no_events,
        'filter_unread': filter_unread,
        'chat_unread_count': chat_unread_count,
        'my_tasks_count': my_tasks_count,
        'ongoing_count': ongoing_count,
        'upcoming_count': upcoming_count,
        'signatures_count': signatures_count,
        'active_referendum': active_referendum,
        'my_tasks': my_tasks,
        'quick_links': quick_links,
        'upcoming_events': upcoming_events,
        'default_asset': default_asset,
        'default_income': default_income,
        'default_expenses': default_expenses,
        'default_balance': default_balance,
        'default_symbol': default_symbol,
        'new_citizens': new_citizens,
        'candidates_count': candidates_count,
        'last_feed_items': last_feed_items,
        'new_proposals': new_proposals,
        'discussed_proposals': discussed_proposals,
    })


def _generate_feed_raw():
    """
    Fetch all feed data WITHOUT user-specific is_read flags.
    Result is cached globally in Redis (TTL 1h). Each item stores
    content_type + object_id so is_read can be attached per-request.
    Invalidated by signals on Post/Task/Decyzja/CitizenActivity/Event/Message.
    """
    cached = cache.get(FEED_CACHE_KEY)
    if cached is not None:
        return cached

    feed_items = []

    posts = Post.objects.filter(updated__gte=timezone.now() - td(days=30)).select_related('author').order_by('-updated')
    for post in posts:
        clean_text = strip_tags(post.text)
        feed_items.append({
            'content_type': 'post',
            'title': post.title,
            'description': clean_text[:125] + '...' if len(clean_text) > 125 else clean_text,
            'author': post.author,
            'timestamp': post.updated,
            'url': f"/board/view/{post.pk}/",
            'object_id': post.pk,
        })

    tasks = Task.objects.filter(updated_at__gte=timezone.now() - td(days=30)).select_related('created_by', 'assigned_to').order_by('-updated_at')
    for task in tasks:
        clean_description = strip_tags(task.description)
        feed_items.append({
            'content_type': 'task',
            'title': task.title,
            'description': clean_description[:125] + '...' if len(clean_description) > 125 else clean_description,
            'author': task.created_by or task.assigned_to,
            'timestamp': task.updated_at,
            'url': f"/tasks/{task.pk}/",
            'object_id': task.pk,
        })

    events = Event.objects.filter(is_active=True).select_related()
    upcoming_events = []
    for event in events:
        next_occurrence = event.get_next_occurrence()
        if next_occurrence and next_occurrence >= timezone.now() - td(days=1):
            upcoming_events.append((event, next_occurrence))
    upcoming_events.sort(key=lambda x: x[1])

    for event, next_occurrence in upcoming_events:
        clean_description = strip_tags(event.description) if event.description else ''
        feed_items.append({
            'content_type': 'event',
            'title': event.title,
            'description': clean_description[:125] + '...' if clean_description and len(clean_description) > 125 else clean_description,
            'author': None,
            'timestamp': next_occurrence,
            'url': f"/events/{event.pk}/",
            'object_id': event.pk,
        })

    # Rooms: per-user (allowed=user) so we keep room items global but mark room_id;
    # is_read attached later per-request from ReadStatus
    all_rooms = Room.objects.prefetch_related(
        'allowed',
        'messages',
        'messages__sender',
    )
    cutoff = timezone.now() - td(days=30)
    for room in all_rooms:
        recent_msgs = sorted(
            [m for m in room.messages.all() if m.time >= cutoff],
            key=lambda m: m.time,
            reverse=True,
        )[:5]
        if recent_msgs:
            latest_message = recent_msgs[0]
            message_list = []
            for msg in reversed(recent_msgs):
                clean_text = strip_tags(msg.text)
                author_name = msg.sender.username if msg.sender else 'System'
                message_list.append(f"- <strong>{author_name}:</strong> {clean_text}")
            allowed_users = list(room.allowed.all())
            feed_items.append({
                'content_type': 'room_messages',
                'title': _("Messages in %(room_title)s") % {
                    'room_title': room.title
                },
                'description': '\n'.join(message_list),
                'author': latest_message.sender,
                'timestamp': latest_message.time,
                'url': f"/chat/#room_id={room.id}",
                'object_id': room.id,
                'room_id': room.id,
                'message_count': len(recent_msgs),
                '_is_public': room.public,
                '_allowed_user_ids': {u.id for u in allowed_users},
                '_allowed_usernames': {u.id: u.username for u in allowed_users},
            })

    decisions = Decyzja.objects.filter(data_ostatniej_modyfikacji__gte=timezone.now() - td(days=30)).order_by('-data_ostatniej_modyfikacji')
    for decision in decisions:
        clean_tresc = strip_tags(decision.tresc) if decision.tresc else ''
        feed_items.append({
            'content_type': 'decision',
            'title': decision.title,
            'description': clean_tresc[:125] + '...' if clean_tresc and len(clean_tresc) > 125 else clean_tresc,
            'author': decision.author,
            'timestamp': decision.data_ostatniej_modyfikacji,
            'url': f"/glosowania/details/{decision.pk}/",
            'object_id': decision.pk,
        })

    citizen_activities = CitizenActivity.objects.filter(timestamp__gte=timezone.now() - td(days=30)).select_related('uzytkownik', 'uzytkownik__uid').order_by('-timestamp')
    for activity in citizen_activities:
        feed_items.append({
            'content_type': 'citizen',
            'title': activity.get_activity_type_display(),
            'description': f"{activity.uzytkownik.uid.username} - {_(activity.description)}",
            'author': activity.uzytkownik.uid,
            'timestamp': activity.timestamp,
            'url': f"/obywatele/{activity.uzytkownik.uid.id}/",
            'object_id': activity.pk,
        })

    events_items = [i for i in feed_items if i['content_type'] == 'event']
    other_items = [i for i in feed_items if i['content_type'] != 'event']
    events_items.sort(key=lambda x: x['timestamp'])
    other_items.sort(key=lambda x: x['timestamp'], reverse=True)
    feed_items = events_items + other_items

    cache.set(FEED_CACHE_KEY, feed_items, FEED_CACHE_TTL)
    return feed_items


def generate_feed_items(user):
    """Generate unified chronological feed for a user, with is_read attached per-request."""
    raw_items = _generate_feed_raw()
    read_status_map = build_read_status_map(user)

    ct_map = {
        'post': ReadStatus.ContentType.POST,
        'task': ReadStatus.ContentType.TASK,
        'event': ReadStatus.ContentType.EVENT,
        'decision': ReadStatus.ContentType.DECISION,
        'citizen': ReadStatus.ContentType.CITIZEN,
    }
    seen_room_ids = set(ReadStatus.objects.filter(
        user=user,
        content_type=ReadStatus.ContentType.MESSAGE,
    ).values_list('object_id', flat=True))

    feed_items = []
    for item in raw_items:
        ct = item['content_type']
        # rooms: filter to rooms the user has access to
        if ct == 'room_messages':
            if not item.get('_is_public') and user.id not in item.get('_allowed_user_ids', set()):
                continue
            if not item.get('_is_public'):
                other = next(
                    (name for uid, name in item.get('_allowed_usernames', {}).items() if uid != user.id),
                    None,
                )
                if other:
                    item = {**item, 'title': _("Messages in %(room_title)s") % {'room_title': other}}
            item = {**item, 'is_read': item['object_id'] in seen_room_ids}
        else:
            rs_ct = ct_map.get(ct)
            is_read = (item['object_id'] in read_status_map[rs_ct]) if rs_ct else False
            item = {
                **item, 'is_read': is_read
            }
        feed_items.append(item)

    return feed_items


@login_required
def activity_page(request):
    all_items = generate_feed_items(request.user)
    unread_count = sum(1 for i in all_items if not i['is_read'])

    # Filter unread only
    filter_unread = request.GET.get('filter') == 'unread'
    if filter_unread:
        all_items = [i for i in all_items if not i['is_read']]

    # Filter by content_type
    ct_filter = request.GET.get('type', '')
    if ct_filter:
        all_items = [i for i in all_items if i['content_type'] == ct_filter]

    # Sort
    sort = request.GET.get('sort', 'date')
    order = request.GET.get('order', 'desc')
    if sort == 'date':
        all_items.sort(key=lambda x: x['timestamp'], reverse=(order == 'desc'))

    content_types = [
        ('', _('All')),
        ('post', _('Announcements')),
        ('task', _('Tasks')),
        ('decision', _('Votings')),
        ('event', _('Calendar')),
        ('citizen', _('Citizens')),
        ('room_messages', _('Chat')),
    ]

    return render(request, 'home/activity.html', {
        'feed_items': all_items,
        'ct_filter': ct_filter,
        'sort': sort,
        'order': order,
        'filter_unread': filter_unread,
        'unread_count': unread_count,
        'content_types': content_types,
    })


@login_required
@require_POST
def mark_as_read(request):
    """Mark a feed item as read"""
    content_type = request.POST.get('content_type')
    object_id = request.POST.get('object_id')

    if not content_type or not object_id:
        return JsonResponse({
            'success': False,
            'error': 'Missing parameters'
        })

    try:
        object_id = int(object_id)
        read_status_content_type = _CONTENT_TYPE_MAP.get(content_type)
        if not read_status_content_type:
            return JsonResponse({
                'success': False,
                'error': 'Invalid content type'
            })

        read_status, created = ReadStatus.objects.get_or_create(user=request.user, content_type=read_status_content_type, object_id=object_id)

        # For room messages, also update room.seen_by for chat consistency
        if content_type in ['message', 'room_messages'] and read_status_content_type == ReadStatus.ContentType.MESSAGE:
            try:
                room = Room.objects.get(id=object_id)
                room.seen_by.add(request.user)
                cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=request.user.id))
            except Room.DoesNotExist:
                pass  # Room might not exist, ignore

        return JsonResponse({
            'success': True
        })

    except (ValueError, KeyError):
        return JsonResponse({
            'success': False,
            'error': 'Invalid parameters'
        })


@login_required
@require_POST
def mark_all_read(request):
    """Mark all feed items as read for the current user"""
    try:
        user = request.user

        # Get all current feed items and mark them as read
        feed_items = generate_feed_items(user)
        # Create read statuses for all unread items
        created_count = 0
        room_ids_to_mark = []  # Collect room IDs for batch update

        for item in feed_items:
            if not item['is_read']:
                read_status_content_type = _CONTENT_TYPE_MAP.get(item['content_type'])
                if read_status_content_type:
                    read_status, created = ReadStatus.objects.get_or_create(user=user, content_type=read_status_content_type, object_id=item['object_id'])
                    if created:
                        created_count += 1

                    # Collect room IDs for batch seen_by update
                    if item['content_type'] in ['message', 'room_messages'] and read_status_content_type == ReadStatus.ContentType.MESSAGE:
                        room_ids_to_mark.append(item['object_id'])

        # Batch update room.seen_by for all rooms
        if room_ids_to_mark:
            try:
                rooms = Room.objects.filter(id__in=room_ids_to_mark)
                for room in rooms:
                    room.seen_by.add(user)
                cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=user.id))
            except Exception as e:
                log.warning(f"Could not update room.seen_by: {e}")

        return JsonResponse({
            'success': True,
            'marked_count': created_count
        })

    except Exception as e:
        log.error(f"Error marking all as read for user {request.user.id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def save_filter_state(request):
    """Save filter state in session"""
    try:
        filter_state = request.POST.get('show_unread_only', 'false').lower() == 'true'
        request.session['show_unread_only'] = filter_state
        request.session.modified = True
        return JsonResponse({
            'success': True
        })
    except Exception as e:
        log.error(f"Error saving filter state: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def mark_unread(request):
    """Mark a feed item as unread"""
    content_type = request.POST.get('content_type')
    object_id = request.POST.get('object_id')

    if not content_type or not object_id:
        return JsonResponse({
            'success': False,
            'error': 'Missing parameters'
        })

    try:
        object_id = int(object_id)
        read_status_content_type = _CONTENT_TYPE_MAP.get(content_type)
        if not read_status_content_type:
            return JsonResponse({
                'success': False,
                'error': 'Invalid content type'
            })

        # Delete read status to mark as unread
        deleted_count, _ = ReadStatus.objects.filter(user=request.user, content_type=read_status_content_type, object_id=object_id).delete()

        # For room messages, also remove from room.seen_by for chat consistency
        if content_type in ['message', 'room_messages'] and read_status_content_type == ReadStatus.ContentType.MESSAGE:
            try:
                room = Room.objects.get(id=object_id)
                room.seen_by.remove(request.user)
                cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=request.user.id))
            except Room.DoesNotExist:
                pass  # Room might not exist, ignore

        return JsonResponse({
            'success': True
        })

    except (ValueError, KeyError):
        return JsonResponse({
            'success': False,
            'error': 'Invalid parameters'
        })


ALL_SEARCH_CATS = ['post', 'task', 'decision', 'event', 'citizen', 'chat']


@login_required
def global_search(request: HttpRequest):
    query = request.GET.get('q', '').strip()

    # Determine active categories.
    # When the request comes from the filter form (filtered=1), an empty
    # selection means the user explicitly deselected every category.
    # Otherwise (e.g. topbar search with no filter UI), empty = search everywhere.
    selected = [c for c in request.GET.getlist('cat') if c in ALL_SEARCH_CATS]
    if request.GET.get('filtered') == '1':
        active_cats = set(selected)
    else:
        active_cats = set(selected) if selected else set(ALL_SEARCH_CATS)

    results = []

    if query:
        # ── Board posts ──────────────────────────────────────────────
        if 'post' in active_cats:
            posts = Post.objects.filter(Q(title__icontains=query) | Q(subtitle__icontains=query) | Q(text__icontains=query)).distinct()[:10]
            for obj in posts:
                results.append({
                    'cat': 'post',
                    'type': _('Post'),
                    'type_color': category_color('post'),
                    'title': obj.title,
                    'description': (strip_tags(obj.text) or '')[:120],
                    'url': f'/board/view/{obj.pk}/',
                })

        # ── Tasks ────────────────────────────────────────────────────
        if 'task' in active_cats:
            tasks = Task.objects.filter(Q(title__icontains=query) | Q(description__icontains=query)).distinct()[:10]
            for obj in tasks:
                results.append({
                    'cat': 'task',
                    'type': _('Task'),
                    'type_color': category_color('task'),
                    'title': obj.title,
                    'description': (strip_tags(obj.description) or '')[:120],
                    'url': f'/tasks/{obj.pk}/',
                })

        # ── Voting / decisions – all statuses ──
        if 'decision' in active_cats:

            # 1. Search main decision fields
            decisions = Decyzja.objects.filter(Q(title__icontains=query) | Q(tresc__icontains=query) | Q(uzasadnienie__icontains=query) | Q(args_for__icontains=query) | Q(args_against__icontains=query)).distinct()[:10]

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
                results.append({
                    'cat': 'decision',
                    'type': _('Voting'),
                    'type_color': category_color('decision'),
                    'title': obj.title,
                    'description': snippet[:120],
                    'meta': (obj.get_status_display() + (f' · {matched_field}' if matched_field else '')),
                    'url': f'/glosowania/details/{obj.pk}/',
                })

            # 2. Search Argument model (user-added arguments across all statuses)
            arguments_qs = DecyzjaArgument.objects.filter(content__icontains=query).select_related('decyzja', 'author').distinct()[:15]

            # seen_decision_ids = {r['url'] for r in results if r['cat'] == 'decision'}
            for arg in arguments_qs:
                arg_type_label = (str(_('argument for')) if arg.argument_type == 'FOR' else str(_('argument against')))
                status_label = arg.decyzja.get_status_display()
                url = f'/glosowania/details/{arg.decyzja.pk}/'
                author_name = arg.author.username if arg.author else str(_('Unknown'))
                results.append({
                    'cat': 'decision',
                    'type': _('Voting'),
                    'type_color': category_color('decision'),
                    'title': arg.decyzja.title,
                    'description': arg.content[:120],
                    'meta': f'{status_label} · {arg_type_label} · {author_name}',
                    'url': url,
                })

        # ── Events ───────────────────────────────────────────────────
        if 'event' in active_cats:
            events = Event.objects.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(place__icontains=query)).distinct()[:10]
            for obj in events:
                results.append({
                    'cat': 'event',
                    'type': _('Event'),
                    'type_color': category_color('event'),
                    'title': obj.title,
                    'description': (strip_tags(obj.description) or '')[:120],
                    'url': f'/events/{obj.pk}/',
                })

        # ── Citizens ─────────────────────────────────────────────────
        if 'citizen' in active_cats:
            users = User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)).distinct()[:10]
            for obj in users:
                results.append({
                    'cat': 'citizen',
                    'type': _('Citizen'),
                    'type_color': category_color('citizen'),
                    'title': obj.get_full_name() or obj.username,
                    'description': f'@{obj.username}',
                    'url': f'/obywatele/{obj.pk}/',
                })

        # ── Chat (rooms + messages user has access to) ────────────────
        if 'chat' in active_cats:
            accessible_rooms = Room.objects.filter(allowed=request.user)

            # Rooms by title
            rooms = accessible_rooms.filter(title__icontains=query).distinct()[:5]
            for obj in rooms:
                results.append({
                    'cat': 'chat',
                    'type': _('Chat'),
                    'type_color': category_color('chat'),
                    'title': obj.displayed_name(request.user),
                    'description': '',
                    'url': f'/chat/#room_id={obj.pk}',
                })

            # Messages in accessible rooms
            messages_qs = Message.objects.filter(
                Q(text__icontains=query),
                room__in=accessible_rooms,
            ).select_related('sender', 'room').order_by('-time').distinct()[:15]
            for obj in messages_qs:
                sender_name = str(_('System')) if obj.sender is None else (str(_('Anonymous')) if obj.anonymous else obj.sender.username)
                results.append({
                    'cat': 'chat',
                    'type': _('Chat message'),
                    'type_color': category_color('chat'),
                    'title': obj.room.displayed_name(request.user),
                    'description': f'{sender_name}: {strip_tags(obj.text)[:100]}',
                    'url': f'/chat/#room_id={obj.room.pk}',
                })

    return render(request, 'home/search.html', {
        'query': query,
        'results': results,
        'active_cats': active_cats,
    })


class RememberLoginView(LoginView):
    form_class = RememberLoginForm
    template_name = 'home/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = form.cleaned_data.get("remember_me")
        if remember:
            self.request.session.set_expiry(getattr(settings, "REMEMBER_ME_COOKIE_AGE", settings.SESSION_COOKIE_AGE))
        else:
            self.request.session.set_expiry(0)
        return response


@login_required
def haslo(request: HttpRequest):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, _('Your password has been changed.'))
            return redirect('obywatele:my_profile')
        else:
            messages.error(request, _('You typed something wrong. See what error appeared above and try again.'))
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'home/haslo.html', {
        'form': form
    })


def manifest(request):
    """Serve dynamic PWA manifest JSON"""
    ss = SiteSettings.get()
    if ss.has_brand_derivatives():
        derived_url = settings.MEDIA_URL + 'site_branding/derived/'
        version_q = f'?v={get_branding_version(ss)}'
        favicon_src = derived_url + 'favicon.ico' + version_q
        icon_192_src = derived_url + 'icon-192.png' + version_q
        icon_512_src = derived_url + 'icon-512.png' + version_q
    else:
        favicon_src = '/static/home/images/favicon.ico'
        icon_192_src = '/static/home/images/icon-192.png'
        icon_512_src = '/static/home/images/icon-512.png'

    from site_settings.params import get_param
    site_name = get_param('site_name') or settings.SITE_NAME
    data = {
        'name': site_name,
        'short_name': site_name[:12],
        'start_url': '/',
        'display': 'standalone',
        'orientation': 'any',
        'theme_color': '#375a7f',
        'background_color': '#000',
        "prefer_related_applications": False,
        "related_applications": [],
        # Required by Chrome on Android for FCM push to work reliably when the PWA
        # is installed to the home screen. 103953800507 is Google's fixed sender ID
        # used for the legacy GCM/FCM handshake; it is NOT your Firebase project ID.
        "gcm_sender_id": "103953800507",
        'icons': [{
            'src': favicon_src,
            'sizes': "16x16 32x32 48x48",
            'type': 'image/x-icon',
            "purpose": "any"
        }, {
            'src': icon_192_src,
            'sizes': "192x192",
            'type': 'image/png',
            "purpose": "any"
        }, {
            'src': icon_512_src,
            'sizes': "512x512",
            'type': 'image/png',
            "purpose": "any"
        }],
    }
    response = JsonResponse(data, json_dumps_params={
        'ensure_ascii': False
    })
    # Let browsers revalidate so PWA name/description changes are picked up
    # without an app restart or manual cache clearing.
    response['Cache-Control'] = 'no-cache'
    return response


def firebase_messaging_sw(request):
    """Serve the Firebase Messaging service worker JavaScript file with injected Firebase config"""
    sw_path = os.path.join(settings.BASE_DIR, 'chat', 'static', 'chat', 'js', 'firebase-messaging-sw.js')

    if not os.path.exists(sw_path):
        return HttpResponse("Firebase Messaging Service Worker not found", status=404)

    with open(sw_path, 'r', encoding='utf-8') as f:
        sw_content = f.read()

    # Inject Firebase config from settings, replacing the entire JS object block
    firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})
    config_str = f"const firebaseConfig = {json.dumps(firebase_config)};"
    sw_content = re.sub(
        r'const\s+firebaseConfig\s*=\s*\{[\s\S]*?\};',
        config_str,
        sw_content,
        count=1,
    )

    response = HttpResponse(sw_content, content_type='application/javascript')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['Service-Worker-Allowed'] = "/"
    return response


def dynamic_settings_js(request: HttpRequest):
    """Serve dynamic JS file with Firebase client config for FCM"""
    firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})
    firebase_vapid_key = getattr(settings, 'FIREBASE_VAPID_KEY', '')
    js_content = f"export const FIREBASE_CONFIG = {json.dumps(firebase_config)};\n"
    js_content += f"export const FIREBASE_VAPID_KEY = {json.dumps(firebase_vapid_key)};\n"
    response = HttpResponse(js_content, content_type='application/javascript')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def site_admin(request: HttpRequest) -> HttpResponse:
    from site_settings.models import QuickLink

    if request.method == 'POST' and 'save_quick_link' in request.POST:
        title = request.POST.get('quick_link_title')
        url = request.POST.get('quick_link_url')
        icon = request.POST.get('quick_link_icon', '')
        order = request.POST.get('quick_link_order', 0)
        if title and url:
            QuickLink.objects.create(title=title, url=url, icon=icon, order=order)
            messages.success(request, _('Link added.'))
        return redirect('site_admin')

    if request.method == 'POST' and 'edit_quick_link' in request.POST:
        link_id = request.POST.get('edit_quick_link')
        title = request.POST.get('quick_link_title')
        url = request.POST.get('quick_link_url')
        icon = request.POST.get('quick_link_icon', '')
        order = request.POST.get('quick_link_order', 0)
        try:
            link = QuickLink.objects.get(id=link_id)
            link.title = title
            link.url = url
            link.icon = icon
            link.order = order
            link.save()
            messages.success(request, _('Link updated.'))
        except QuickLink.DoesNotExist:
            messages.error(request, _("Link doesn't exist."))
        return redirect('site_admin')

    if request.method == 'POST' and 'reorder_quick_links' in request.POST:
        order_data = json.loads(request.POST.get('order', '[]'))
        for index, link_id in enumerate(order_data):
            try:
                link = QuickLink.objects.get(id=link_id)
                link.order = index
                link.save()
            except QuickLink.DoesNotExist:
                continue
        return JsonResponse({'ok': True})

    if request.method == 'POST' and 'delete_quick_link' in request.POST:
        link_id = request.POST.get('delete_quick_link')
        try:
            link = QuickLink.objects.get(id=link_id)
            link.delete()
            messages.success(request, _('Link deleted.'))
        except QuickLink.DoesNotExist:
            messages.error(request, _("Link doesn't exist."))
        return redirect('site_admin')

    quick_links = QuickLink.objects.all()

    return render(request, 'home/site_admin.html', {
        'quick_links': quick_links,
    })

