"""Reusable calendar helpers — used by `/events/` (this app) and the desktop calendar tile."""

import calendar as _cal
from datetime import date, datetime, timedelta

from django.utils import timezone


def month_bounds(year, month):
    end_y, end_m = (year + 1, 1) if month == 12 else (year, month + 1)
    start = timezone.make_aware(datetime(year, month, 1))
    end = timezone.make_aware(datetime(end_y, end_m, 1)) - timedelta(microseconds=1)
    return start, end


def build_calendar_grid(year, month, events):
    """Return a list of weeks; each week is a list of cell dicts:
        {'day': int|None, 'events': [Event,...], 'is_today': bool, 'iso_date': 'YYYY-MM-DD'|None}
    Days from adjacent months are represented as None.
    Handles all Event.frequency variants (once/daily/weekly/monthly/monthly_ordinal/yearly).
    """
    today = timezone.localdate()
    range_start, range_end = month_bounds(year, month)
    events_by_day = {}
    for event in events:
        for occurrence in event.get_occurrences(range_start, range_end):
            local_occurrence = timezone.localtime(occurrence)
            events_by_day.setdefault(local_occurrence.day, []).append(event)

    raw_weeks = _cal.monthcalendar(year, month)
    weeks = []
    for raw_week in raw_weeks:
        week = []
        for day_num in raw_week:
            if day_num == 0:
                week.append({'day': None, 'events': [], 'is_today': False, 'iso_date': None})
            else:
                week.append({'day': day_num, 'events': events_by_day.get(day_num, []), 'is_today': date(year, month, day_num) == today, 'iso_date': f'{year}-{month:02d}-{day_num:02d}'})
        weeks.append(week)
    return weeks


def parse_month_param(month_param):
    """Parse 'YYYY-MM' GET param into (year, month) tuple, fallback to current month."""
    now = timezone.localtime(timezone.now())
    try:
        y, m = (int(x) for x in (month_param or '').split('-'))
        if not (1 <= m <= 12):
            raise ValueError
        return y, m
    except (ValueError, AttributeError):
        return now.year, now.month


def adjacent_months(year, month):
    """Return ('YYYY-MM' for prev, 'YYYY-MM' for next)."""
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    return f'{prev_y}-{prev_m:02d}', f'{next_y}-{next_m:02d}'


def year_options(year, radius=5):
    """Return a bounded list of years centered on the selected year."""
    return range(year - radius, year + radius + 1)
