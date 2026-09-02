from datetime import date
from datetime import timedelta as td

from django.utils import timezone

from .calendar import adjacent_months, build_calendar_grid, parse_month_param
from .models import Event


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for events (upcoming occurrences + calendar grid)."""
    today_dt = timezone.now()
    events_horizon_end = today_dt + td(days=90)

    occurrences = []
    for event in Event.objects.filter(is_active=True):
        event_occurrences = event.get_occurrences(today_dt, events_horizon_end)
        if event_occurrences:
            occurrences.append({'event': event, 'date': event_occurrences[0]})
    occurrences.sort(key=lambda o: o['date'])
    upcoming_events = occurrences[:5]

    cal_year, cal_month = parse_month_param(month_param)
    cal_weeks = build_calendar_grid(cal_year, cal_month, Event.objects.filter(is_active=True))
    prev_month, next_month = adjacent_months(cal_year, cal_month)

    return {
        'upcoming_events': upcoming_events,
        'cal_year': cal_year,
        'cal_month': cal_month,
        'cal_first_day': date(cal_year, cal_month, 1),
        'cal_weeks': cal_weeks,
        'prev_month': prev_month,
        'next_month': next_month,
    }
