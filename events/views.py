from datetime import date as _date
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from core.signals import event_created, event_updated
from core.utils import build_detail_navigation, build_site_url
from home.navigation import default_toolbar_views

from .calendar import adjacent_months, build_calendar_grid, month_bounds, parse_month_param, year_options
from .forms import EventForm
from .models import Event


def _visible_events(request):
    events = Event.objects.filter(is_active=True)
    return events if request.user.is_authenticated else events.filter(is_public=True)


def _events_stepper():
    return {'steps': [{'url': reverse('events:list'), 'icon': 'calendar', 'label': gettext_lazy('Calendar'), 'active': True}]}


EVENTS_FUTURE_DAYS = 31


def _occurrences_between(request, range_start, range_end):
    now = timezone.now()
    occurrences = []
    for event in _visible_events(request):
        for occurrence in event.get_occurrences(range_start, range_end):
            month = timezone.localtime(occurrence).strftime('%Y-%m')
            detail_url = reverse('events:detail', kwargs={'pk': event.pk})
            detail_url = f"{detail_url}?{urlencode({'month': month, 'occurrence': occurrence.isoformat()})}"
            occurrences.append({'event': event, 'date': occurrence, 'is_past': occurrence < now, 'detail_url': detail_url})
    return sorted(occurrences, key=lambda item: item['date'])


def _month_occurrences(request, year, month):
    return _occurrences_between(request, *month_bounds(year, month))


def _list_occurrences(request, year, month):
    range_start, _ = month_bounds(year, month)
    future_end = timezone.localdate() + timedelta(days=EVENTS_FUTURE_DAYS)
    range_end = timezone.make_aware(datetime.combine(future_end, time.max))
    return _occurrences_between(request, range_start, range_end)


class EventListView(ListView):
    """Renders selected-month occurrences through the rolling future window."""

    template_name = 'events/event_list.html'
    context_object_name = 'occurrences'

    def get_queryset(self):
        year, month = parse_month_param(self.request.GET.get('month', ''))
        return _list_occurrences(self.request, year, month)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        local_now = timezone.localtime(now)
        context['now'] = now

        # Pre-render the selected month's mini-calendar grid.
        cal_year, cal_month = parse_month_param(self.request.GET.get('month', ''))
        events_qs = _visible_events(self.request)
        prev_month, next_month = adjacent_months(cal_year, cal_month)
        toolbar_views = default_toolbar_views()

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
                'stepper': _events_stepper(),
            }
        )
        return context


def events_agenda_chunk(request: HttpRequest):
    """AJAX: returns the agenda partial for the selected month and future window."""
    year, month = parse_month_param(request.GET.get('month', ''))
    occurrences = _list_occurrences(request, year, month)
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cal_year, cal_month = parse_month_param(self.request.GET.get('month', ''))
        occurrences = _month_occurrences(self.request, cal_year, cal_month)
        occurrence = parse_datetime(self.request.GET.get('occurrence', ''))
        current_item = next((item for item in occurrences if item['event'].pk == self.object.pk and (occurrence is None or item['date'] == occurrence)), None)
        current_key = None
        if current_item:
            current_key = (current_item['event'].pk, current_item['date'].isoformat())

        def occurrence_query(item):
            params = self.request.GET.copy()
            params['occurrence'] = item['date'].isoformat()
            return params.urlencode()

        context.update(
            build_detail_navigation(
                self.request,
                occurrences,
                current_key,
                'events:detail',
                item_key=lambda item: (item['event'].pk, item['date'].isoformat()),
                url_kwargs=lambda item: {'pk': item['event'].pk},
                query_string_for_item=occurrence_query,
            )
        )

        context['stepper'] = _events_stepper()
        return context


class EventFormViewMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stepper'] = _events_stepper()
        return context


class EventCreateView(EventFormViewMixin, LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:list')

    def get_initial(self):
        initial = super().get_initial()
        try:
            selected_date = parse_date(self.request.GET.get('date', ''))
        except ValueError:
            selected_date = None
        start_date = selected_date or timezone.localdate()
        initial['start_date'] = timezone.make_aware(datetime.combine(start_date, time(hour=12)))
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        event = self.object
        event_url = build_site_url(event.get_absolute_url())
        transaction.on_commit(lambda: event_created.send(sender=Event, event=event, url=event_url))
        return response


class EventUpdateView(EventFormViewMixin, LoginRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:list')

    def form_valid(self, form):
        response = super().form_valid(form)
        event = self.object
        event_url = build_site_url(event.get_absolute_url())
        transaction.on_commit(lambda: event_updated.send(sender=Event, event=event, url=event_url))
        return response


class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    success_url = reverse_lazy('events:list')

    def get(self, request, *args, **kwargs):
        return redirect('events:detail', pk=kwargs['pk'])
