import logging
from datetime import date
from datetime import timedelta as td
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from bookkeeping.models import Asset
from bookkeeping.services import asset_balances
from chat.models import Message
from chat.services import get_unread_count_for_user
from events.calendar import adjacent_months, build_calendar_grid, parse_month_param
from events.models import Event
from glosowania.models import Decyzja, KtoJuzGlosowal
from obywatele.models import Uzytkownik
from site_settings.models import QuickLink
from tasks.models import Task

from .feed import generate_feed_items, get_unread_count

log = logging.getLogger(__name__)


def build_dashboard_context(user, feed_items=None, filter_unread=False, month_param=''):
    """Build the full context dict for the home/dashboard view."""
    if feed_items is None:
        feed_items = generate_feed_items(user)

    request_unread_count = get_unread_count(user, feed_items)

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

    # My tasks widget (max 3, active — only where the viewer is the coordinator)
    my_tasks = Task.objects.filter(assigned_to=user, status=Task.Status.ACTIVE).order_by('updated_at')[:3]

    # Active referendum widget
    active_referendum = None
    referendum_obj = Decyzja.objects.filter(status=Decyzja.Status.REFERENDUM).select_related('author').order_by('-data_referendum_start').first()
    if referendum_obj and referendum_obj.data_referendum_start and referendum_obj.data_referendum_stop:
        today = timezone.now().date()
        days_remaining = max(0, (referendum_obj.data_referendum_stop - today).days)
        total_days = max(1, (referendum_obj.data_referendum_stop - referendum_obj.data_referendum_start).days)
        time_pct = min(100, round(days_remaining / total_days * 100))
        if time_pct > 50:
            bar_color = 'success'
        elif time_pct >= 20:
            bar_color = 'warning'
        else:
            bar_color = 'danger'
        user_voted = KtoJuzGlosowal.objects.filter(projekt=referendum_obj, ktory_uzytkownik_juz_zaglosowal=user).exists()
        active_referendum = {'obj': referendum_obj, 'days_remaining': days_remaining, 'total_days': total_days, 'time_pct': time_pct, 'bar_color': bar_color, 'user_voted': user_voted}

    # Kalendarz: najbliższe wystąpienia (dla każdego wydarzenia tylko jedno najbliższe)
    today_dt = timezone.now()
    _events_horizon_end = today_dt + td(days=90)
    _occurrences = []
    for _ev in Event.objects.filter(is_active=True):
        _event_occurrences = _ev.get_occurrences(today_dt, _events_horizon_end)
        if _event_occurrences:
            _occurrences.append({'event': _ev, 'date': _event_occurrences[0]})
    _occurrences.sort(key=lambda o: o['date'])
    upcoming_events = _occurrences[:5]

    # Finanse: salda CAŁEJ historii w walucie domyślnej (default asset).
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

    # Nowi ludzie: 6 ostatnio dołączonych kandydatów
    new_people = list(Uzytkownik.objects.filter(uid__is_active=False).select_related('uid').order_by('-uid__date_joined')[:7])

    # Community stats
    pop = User.objects.filter(is_active=True).count()
    thirty_days_ago = timezone.now() - td(days=30)
    active_last_month = User.objects.filter(is_active=True, last_login__gte=thirty_days_ago).count()
    active_pct = round(active_last_month / pop * 100) if pop else 0

    skills_knowledge_hobby_count = Uzytkownik.objects.exclude(skills_knowledge_hobby__isnull=True).exclude(skills_knowledge_hobby='').count()
    give_away_count = Uzytkownik.objects.exclude(to_give_away__isnull=True).exclude(to_give_away='').count()
    borrow_count = Uzytkownik.objects.exclude(to_borrow__isnull=True).exclude(to_borrow='').count()
    for_sale_count = Uzytkownik.objects.exclude(for_sale__isnull=True).exclude(for_sale='').count()

    recent_chat_messages = Message.objects.filter(room__public=True, room__allowed=user).select_related('sender', 'sender__uzytkownik', 'room').order_by('-time')[:4]

    # Calendar month grid
    cal_year, cal_month = parse_month_param(month_param)
    cal_weeks = build_calendar_grid(cal_year, cal_month, Event.objects.filter(is_active=True))
    prev_month, next_month = adjacent_months(cal_year, cal_month)

    last_feed_items = [i for i in feed_items if i['content_type'] != 'event'][:6]

    # Unread count without events (for home page display)
    unread_items_no_events = [item for item in feed_items if not item['is_read'] and item['content_type'] != 'event']

    chat_unread_count = get_unread_count_for_user(user)

    # Licznik aktywnych zadań użytkownika
    my_tasks_count = Task.objects.filter(Q(assigned_to=user) | Q(votes__user=user, votes__value=1), status=Task.Status.ACTIVE).distinct().count()

    quick_links = list(QuickLink.objects.order_by('order'))

    return {
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
        'new_people': new_people,
        'last_feed_items': last_feed_items,
        'new_proposals': new_proposals,
        'discussed_proposals': discussed_proposals,
        'active_pct': active_pct,
        'skills_knowledge_hobby_count': skills_knowledge_hobby_count,
        'skills_count': skills_knowledge_hobby_count,
        'knowledge_count': skills_knowledge_hobby_count,
        'give_away_count': give_away_count,
        'borrow_count': borrow_count,
        'for_sale_count': for_sale_count,
        'recent_chat_messages': recent_chat_messages,
        'cal_weeks': cal_weeks,
        'cal_year': cal_year,
        'cal_month': cal_month,
        'cal_first_day': date(cal_year, cal_month, 1),
        'prev_month': prev_month,
        'next_month': next_month,
        '_unread_count': request_unread_count,
    }
