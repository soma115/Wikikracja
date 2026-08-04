from datetime import date as _date
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .calendar import adjacent_months, build_calendar_grid, parse_month_param
from .forms import EventForm
from .models import Event

# Horizon for expanding recurring events into individual occurrences on the list view.
EVENTS_LIST_PAST_DAYS = 30
EVENTS_LIST_FUTURE_DAYS = 90


class EventListView(ListView):
    """Renders an agenda-style list of all occurrences in [now-PAST .. now+FUTURE]
    horizon. Day clicks in the calendar widget scroll to in-page anchors
    `#day-YYYY-MM-DD` (no server-side day filter)."""
    template_name = 'events/event_list.html'
    context_object_name = 'occurrences'

    def get_queryset(self):
        queryset = Event.objects.filter(is_active=True)
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_public=True)

        now = timezone.now()
        range_start = now - timedelta(days=EVENTS_LIST_PAST_DAYS)
        range_end = now + timedelta(days=EVENTS_LIST_FUTURE_DAYS)

        occurrences = []
        for event in queryset:
            for date in event.get_occurrences(range_start, range_end):
                occurrences.append({
                    'event': event,
                    'date': date,
                    'is_past': date < now,
                })
        occurrences.sort(key=lambda o: o['date'])
        return occurrences

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        context['now'] = now

        # Pre-render current month's mini-calendar grid so the drawer for the
        # current-month header opens instantly without an AJAX round trip.
        local_now = timezone.localtime(now)
        events_qs = Event.objects.filter(is_active=True)
        if not self.request.user.is_authenticated:
            events_qs = events_qs.filter(is_public=True)
        prev_month, next_month = adjacent_months(local_now.year, local_now.month)
        context.update({
            'current_month_iso': f'{local_now.year}-{local_now.month:02d}',
            'current_month_weeks': build_calendar_grid(local_now.year, local_now.month, events_qs),
            'current_month_first_day': _date(local_now.year, local_now.month, 1),
            'current_month_year': local_now.year,
            'current_month_num': local_now.month,
            'current_month_prev': prev_month,
            'current_month_next': next_month,
        })
        return context


def events_agenda_chunk(request: HttpRequest):
    """AJAX: returns a 3-month agenda partial starting from the given month."""
    cal_year, cal_month = parse_month_param(request.GET.get('month', ''))

    end_y, end_m = cal_year, cal_month + 3
    if end_m > 12:
        end_m -= 12
        end_y += 1

    range_start = timezone.make_aware(datetime(cal_year, cal_month, 1))
    range_end = timezone.make_aware(datetime(end_y, end_m, 1))

    events_qs = Event.objects.filter(is_active=True)
    if not request.user.is_authenticated:
        events_qs = events_qs.filter(is_public=True)

    now = timezone.now()
    occurrences = []
    for event in events_qs:
        for occ_date in event.get_occurrences(range_start, range_end):
            occurrences.append({'event': event, 'date': occ_date, 'is_past': occ_date < now})
    occurrences.sort(key=lambda o: o['date'])

    return render(request, 'events/_agenda_chunk.html', {'occurrences': occurrences, 'now': now})


def calendar_partial_context(request: HttpRequest, events_qs=None):
    """Build context dict for the shared month-grid partial."""
    cal_year, cal_month = parse_month_param(request.GET.get('month', ''))
    if events_qs is None:
        events_qs = Event.objects.filter(is_active=True)
    if not request.user.is_authenticated:
        events_qs = events_qs.filter(is_public=True)
    cal_weeks = build_calendar_grid(cal_year, cal_month, events_qs)
    prev_month, next_month = adjacent_months(cal_year, cal_month)
    return {
        'cal_weeks': cal_weeks,
        'cal_year': cal_year,
        'cal_month': cal_month,
        'cal_first_day': _date(cal_year, cal_month, 1),
        'prev_month': prev_month,
        'next_month': next_month,
    }


def events_calendar(request: HttpRequest):
    """Renders just the month-grid partial. AJAX-loaded by the events list page (and reused
    by `obywatele:wspolnota_calendar`)."""
    return render(request, 'obywatele/_calendar_partial.html', calendar_partial_context(request))


class EventDetailView(DetailView):
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'

    def get_queryset(self):
        queryset = super().get_queryset()

        # If user is not authenticated, show only public events
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_public=True)

        return queryset


class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:list')


class EventUpdateView(LoginRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:list')


class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    template_name = 'events/event_confirm_delete.html'
    success_url = reverse_lazy('events:list')
