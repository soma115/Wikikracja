# Events Module

A simple Django app for managing cyclical events in the Wikikracja project.

## Features

- **Simple Event Management**: Create, view, edit, and delete events
- **Cyclical Events**: Support for one-time, daily, weekly, monthly, ordinal-monthly, and yearly recurring events
- **Monthly Calendar**: Permanent mini-calendar with month navigation, year selection, and event markers
- **Agenda and Grid Views**: Displays past and upcoming occurrences from the selected month
- **Bootstrap UI**: Clean, responsive interface using Bootstrap 5 and django-crispy-forms
- **No Participant Management**: Focus on event scheduling only

## Models

### Event
- `title`: Event name
- `description`: Optional event description
- `start_date`: When the event starts
- `end_date`: Optional end date
- `frequency`: One-time, daily, weekly, monthly, or yearly
- `is_active`: Whether the event is currently active

## URLs

- `/events/` - Calendar and active event occurrences for the selected month
- `/events/<id>/` - View event details
- `/events/create/` - Create new event (requires login)
- `/events/<id>/edit/` - Edit event (requires login)
- `/events/<id>/delete/` - Delete event (requires login)

## Usage

1. Navigate to the Events section in the main navigation
2. Select a month with the calendar arrows and a year from the year selector
3. View that month's occurrences in the agenda or grid layout
4. Select a calendar day to focus the list from that date
5. Click an event to see full details
6. Logged-in users can create, edit, and delete events

## Admin Interface

Events can also be managed through the Django admin interface with:
- List view with filtering and search
- Organized fieldsets for easy editing
- Date hierarchy for navigation

## Testing

Run tests with:
```bash
python manage.py test events
```

The module includes comprehensive tests for both models and views.
