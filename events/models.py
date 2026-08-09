import calendar
from datetime import timedelta
from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Event(models.Model):
    FREQUENCY_CHOICES = [('once', _('One-time')), ('daily', _('Daily')), ('weekly', _('Weekly')), ('monthly', _('Monthly')), ('monthly_ordinal', _('Monthly (specific weekday)')), ('yearly', _('Yearly'))]

    ORDINAL_CHOICES = [(1, _('First')), (2, _('Second')), (3, _('Third')), (4, _('Fourth')), (-1, _('Last'))]

    WEEKDAY_CHOICES = [(0, _('Monday')), (1, _('Tuesday')), (2, _('Wednesday')), (3, _('Thursday')), (4, _('Friday')), (5, _('Saturday')), (6, _('Sunday'))]

    title = models.CharField(max_length=200, verbose_name=_('Title'), help_text=_('Enter a descriptive name for the event'))
    description = models.TextField(blank=True, verbose_name=_('Description'), help_text=_('Optional description of the event'))
    link = models.URLField(blank=True, verbose_name=_('Link to the meeting'), help_text=_('Optional link to event details, registration, or location'))
    place = models.CharField(max_length=200, blank=True, verbose_name=_('Place'), help_text=_('Optional event location or venue'))
    start_date = models.DateTimeField(verbose_name=_('Start Date'), help_text=_('When does the event start?'))
    end_date = models.DateTimeField(blank=True, null=True, verbose_name=_('End Date'), help_text=_('When does the event end? (optional)'))
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='once', verbose_name=_('Frequency'), help_text=_('How often does this event repeat?'))
    monthly_ordinal = models.IntegerField(blank=True, null=True, choices=ORDINAL_CHOICES, verbose_name=_('Week of month'), help_text=_('For monthly ordinal events: which week? (e.g., First, Second, Last)'))
    monthly_weekday = models.IntegerField(
        blank=True, null=True, choices=WEEKDAY_CHOICES, verbose_name=_('Day of week'), help_text=_('For monthly ordinal events: which day of the week? (e.g., Monday, Tuesday)')
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Active'), help_text=_('Uncheck to disable this event'))
    is_public = models.BooleanField(default=True, verbose_name=_('Public'), help_text=_('Public events are visible to everyone. Private events are only visible to logged-in users.'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date']
        verbose_name = _('Event')
        verbose_name_plural = _('Events')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('events:detail', kwargs={'pk': self.pk})

    def _get_nth_weekday_of_month(self, year, month, weekday, nth):
        """
        Get the date of the nth occurrence of a weekday in a month.
        Args:
            year: Year
            month: Month (1-12)
            weekday: Weekday (0=Monday, 6=Sunday)
            nth: Which occurrence (1=first, 2=second, etc., -1=last)
        Returns:
            datetime object or None if invalid
        """
        # Get all days in the month
        month_calendar = calendar.monthcalendar(year, month)

        if nth == -1:
            # Get the last occurrence
            for week in reversed(month_calendar):
                if week[weekday] != 0:
                    day = week[weekday]
                    # Combine with the time from start_date
                    result = self.start_date.replace(year=year, month=month, day=day)
                    # Ensure timezone-aware after replace
                    if timezone.is_naive(result):
                        result = timezone.make_aware(result)
                    return result
        else:
            # Get the nth occurrence (1-indexed)
            occurrence_count = 0
            for week in month_calendar:
                if week[weekday] != 0:
                    occurrence_count += 1
                    if occurrence_count == nth:
                        day = week[weekday]
                        # Combine with the time from start_date
                        result = self.start_date.replace(year=year, month=month, day=day)
                        # Ensure timezone-aware after replace
                        if timezone.is_naive(result):
                            result = timezone.make_aware(result)
                        return result

        return None

    def get_next_occurrence(self):
        """Get the next occurrence of this event based on frequency"""
        if self.frequency == 'once':
            return self.start_date if self.start_date > timezone.now() else None

        now = timezone.now()
        next_date = self.start_date

        if self.frequency == 'daily':
            while next_date <= now:
                next_date += timedelta(days=1)
        elif self.frequency == 'weekly':
            while next_date <= now:
                next_date += timedelta(weeks=1)
        elif self.frequency == 'monthly':
            while next_date <= now:
                if next_date.month == 12:
                    next_date = next_date.replace(year=next_date.year + 1, month=1)
                else:
                    next_date = next_date.replace(month=next_date.month + 1)
                # Ensure timezone-aware after replace
                if timezone.is_naive(next_date):
                    next_date = timezone.make_aware(next_date)
        elif self.frequency == 'monthly_ordinal':
            # For monthly ordinal, we need to find the next occurrence of the specified weekday
            if self.monthly_ordinal is None or self.monthly_weekday is None:
                return None

            # Start from the current month
            year = now.year
            month = now.month

            # Find the next occurrence
            while True:
                next_date = self._get_nth_weekday_of_month(year, month, self.monthly_weekday, self.monthly_ordinal)

                if next_date and next_date > now:
                    break

                # Move to next month
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1

                # Safety check to avoid infinite loop
                if year > now.year + 10:
                    return None
        elif self.frequency == 'yearly':
            while next_date <= now:
                next_date = next_date.replace(year=next_date.year + 1)
                # Ensure timezone-aware after replace
                if timezone.is_naive(next_date):
                    next_date = timezone.make_aware(next_date)

        return next_date

    def is_upcoming(self):
        """Check if event has upcoming occurrences"""
        if not self.is_active:
            return False
        return self.get_next_occurrence() is not None

    def get_occurrences(self, range_start, range_end):
        """Return all occurrences of this event between range_start and range_end (inclusive).

        range_start and range_end are timezone-aware datetimes. Used to expand
        recurring events into individual dated entries for list/calendar views.
        """
        if range_end < range_start:
            return []

        if self.frequency == 'once':
            if range_start <= self.start_date <= range_end:
                return [self.start_date]
            return []

        if self.start_date > range_end:
            return []

        occurrences = []

        if self.frequency == 'daily':
            current = self.start_date
            if current < range_start:
                days_diff = (range_start - current).days
                current = current + timedelta(days=days_diff)
            safety = 0
            while current <= range_end and safety < 5000:
                if current >= range_start:
                    occurrences.append(current)
                current += timedelta(days=1)
                safety += 1

        elif self.frequency == 'weekly':
            current = self.start_date
            if current < range_start:
                weeks_diff = (range_start - current).days // 7
                current = current + timedelta(weeks=weeks_diff)
            safety = 0
            while current <= range_end and safety < 1000:
                if current >= range_start:
                    occurrences.append(current)
                current += timedelta(weeks=1)
                safety += 1

        elif self.frequency == 'monthly':
            current = self.start_date
            safety = 0
            while current <= range_end and safety < 1200:
                if current >= range_start:
                    occurrences.append(current)
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
                if timezone.is_naive(current):
                    current = timezone.make_aware(current)
                safety += 1

        elif self.frequency == 'monthly_ordinal':
            if self.monthly_ordinal is None or self.monthly_weekday is None:
                return []
            iter_from = self.start_date if self.start_date > range_start else range_start
            year = iter_from.year
            month = iter_from.month
            safety = 0
            while safety < 1200:
                occ = self._get_nth_weekday_of_month(year, month, self.monthly_weekday, self.monthly_ordinal)
                if occ is None:
                    pass
                elif occ > range_end:
                    break
                elif occ >= range_start and occ >= self.start_date:
                    occurrences.append(occ)
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1
                if year > range_end.year + 1:
                    break
                safety += 1

        elif self.frequency == 'yearly':
            current = self.start_date
            safety = 0
            while current <= range_end and safety < 100:
                if current >= range_start:
                    occurrences.append(current)
                current = current.replace(year=current.year + 1)
                if timezone.is_naive(current):
                    current = timezone.make_aware(current)
                safety += 1

        return occurrences

    @property
    def google_calendar_url(self):
        """
        Generate a Google Calendar URL for this event.
        Returns:
            URL string for adding event to Google Calendar
        """
        # Use the original start date for the event
        event_date = self.start_date

        # Make sure we're working with timezone-aware datetime
        if timezone.is_naive(event_date):
            event_date = timezone.make_aware(event_date)

        # Format dates for Google Calendar (yyyyMMddTHHmmssZ format)
        # Convert to UTC for consistency
        event_date_utc = event_date.astimezone(dt_timezone.utc)
        start_dt = event_date_utc.strftime('%Y%m%dT%H%M%SZ')

        # Calculate end date
        if self.end_date:
            # Use the time difference from original start/end
            duration = self.end_date - self.start_date
            end_date = event_date + duration
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)
            end_date_utc = end_date.astimezone(dt_timezone.utc)
            end_dt = end_date_utc.strftime('%Y%m%dT%H%M%SZ')
        else:
            # Default to 1 hour duration
            end_date = event_date + timedelta(hours=1)
            end_date_utc = end_date.astimezone(dt_timezone.utc)
            end_dt = end_date_utc.strftime('%Y%m%dT%H%M%SZ')

        # Build description with link if available
        description = self.description or ''
        if self.link:
            description = f"{description}\n\nLink: {self.link}" if description else f"Link: {self.link}"

        # Build location
        location = self.place if self.place else ''

        # Build recurrence rule for Google Calendar
        recurrence = None
        if self.frequency == 'daily':
            recurrence = 'RRULE:FREQ=DAILY'
        elif self.frequency == 'weekly':
            recurrence = 'RRULE:FREQ=WEEKLY'
        elif self.frequency == 'monthly':
            recurrence = 'RRULE:FREQ=MONTHLY'
        elif self.frequency == 'monthly_ordinal' and self.monthly_ordinal and self.monthly_weekday is not None:
            # Convert weekday (0=Monday) to Google Calendar format (SU, MO, TU, WE, TH, FR, SA)
            weekday_map = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
            weekday_str = weekday_map[self.monthly_weekday]
            ordinal = self.monthly_ordinal
            recurrence = f'RRULE:FREQ=MONTHLY;BYDAY={ordinal}{weekday_str}'
        elif self.frequency == 'yearly':
            recurrence = 'RRULE:FREQ=YEARLY'

        # Build parameters for new Google Calendar URL format
        params = {'action': 'TEMPLATE', 'text': self.title, 'dates': f'{start_dt}/{end_dt}'}

        # Only add non-empty optional parameters
        if description:
            params['details'] = description
        if location:
            params['location'] = location
        if recurrence:
            params['recur'] = recurrence

        # Generate URL - use the new calendar.google.com/calendar/u/0/r/eventedit format
        base_url = 'https://calendar.google.com/calendar/render'
        return f'{base_url}?{urlencode(params)}'
