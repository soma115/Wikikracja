# Events Module

A simple Django app for managing cyclical events in the Wikikracja project.

## Features

- **Simple Event Management**: Create, view, edit, and delete events
- **Cyclical Events**: Support for one-time, daily, weekly, monthly, and yearly recurring events
- **Bootstrap UI**: Clean, responsive interface using Bootstrap 4 and django-crispy-forms
- **Built-in Views**: Uses Django's built-in class-based views for simplicity
- **No User Configuration**: Keeps things simple with no per-user settings
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

- `/events/` - List all active events
- `/events/<id>/` - View event details
- `/events/create/` - Create new event (requires login)
- `/events/<id>/edit/` - Edit event (requires login)
- `/events/<id>/delete/` - Delete event (requires login)

## Usage

1. Navigate to the Events section in the main navigation
2. View all active events in a card-based layout
3. Click on any event to see full details
4. Logged-in users can create, edit, and delete events
5. For recurring events, the system calculates the next occurrence automatically

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
