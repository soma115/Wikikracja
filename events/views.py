from datetime import date as _date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .calendar import adjacent_months, build_calendar_grid, month_bounds, parse_month_param, year_options
from .forms import EventForm
from .models import Event


def _visible_events(request):
    events = Event.objects.filter(is_active=True)
    return events if request.user.is_authenticated else events.filter(is_public=True)


def _month_occurrences(request, year, month):
    range_start, range_end = month_bounds(year, month)
    events = _visible_events(request)

    now = timezone.now()
    occurrences = [{'event': event, 'date': occurrence, 'is_past': occurrence < now} for event in events for occurrence in event.get_occurrences(range_start, range_end)]
    return sorted(occurrences, key=lambda item: item['date'])


class EventListView(ListView):
    """Renders an agenda-style list of all occurrences in the selected month.
    Day clicks in the calendar widget scroll to in-page anchors
    `#day-YYYY-MM-DD`."""

    template_name = 'events/event_list.html'
    context_object_name = 'occurrences'

    def get_queryset(self):
        cal_year, cal_month = parse_month_param(self.request.GET.get('month', ''))
        return _month_occurrences(self.request, cal_year, cal_month)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        local_now = timezone.localtime(now)
        context['now'] = now

        # Pre-render the selected month's mini-calendar grid.
        cal_year, cal_month = parse_month_param(self.request.GET.get('month', ''))
        events_qs = _visible_events(self.request)
        prev_month, next_month = adjacent_months(cal_year, cal_month)
        toolbar_views = [{'name': 'list', 'icon': 'list', 'title': gettext_lazy('List')}, {'name': 'grid', 'icon': 'grip', 'title': gettext_lazy('Grid')}]

        context.update(
            {
                'current_month_iso': f'{cal_year}-{cal_month:02d}',
                'today_month_iso': f'{local_now.year}-{local_now.month:02d}',
                'current_month_weeks': build_calendar_grid(cal_year, cal_month, events_qs),
                'current_month_first_day': _date(cal_year, cal_month, 1),
                'current_month_year': cal_year,
                'current_month_num': cal_month,
                'current_month_prev': prev_month,
                'current_month_next': next_month,
                'year_options': year_options(cal_year),
                'toolbar_views': toolbar_views,
            }
        )
        return context


def events_agenda_chunk(request: HttpRequest):
    """AJAX: returns an agenda partial for the given month."""
    cal_year, cal_month = parse_month_param(request.GET.get('month', ''))

    occurrences = _month_occurrences(request, cal_year, cal_month)
    return render(request, 'events/_agenda_chunk.html', {'occurrences': occurrences, 'now': timezone.now(), 'include_grid_chunk': True})


def calendar_partial_context(request: HttpRequest, events_qs=None):
    """Build context dict for the shared month-grid partial."""
    cal_year, cal_month = parse_month_param(request.GET.get('month', ''))
    if events_qs is None:
        events_qs = _visible_events(request)
    elif not request.user.is_authenticated:
        events_qs = events_qs.filter(is_public=True)
    cal_weeks = build_calendar_grid(cal_year, cal_month, events_qs)
    prev_month, next_month = adjacent_months(cal_year, cal_month)
    context = {'cal_weeks': cal_weeks, 'cal_year': cal_year, 'cal_month': cal_month, 'cal_first_day': _date(cal_year, cal_month, 1), 'prev_month': prev_month, 'next_month': next_month}
    if request.GET.get('picker') == '1':
        context['year_options'] = year_options(cal_year)
    return context


def events_calendar(request: HttpRequest):
    """Renders just the month-grid partial. AJAX-loaded by the events list page and the desktop calendar tile."""
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
