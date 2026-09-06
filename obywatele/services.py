from datetime import datetime, timezone

from django.utils.translation import gettext_lazy as _

from chat.services import get_user_created_room_items
from glosowania import activity as voting_activity
from tasks import activity as task_activity

from .models import CitizenActivity


def _sort_activity_items(items):
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    items.sort(key=lambda item: item['ts'] or epoch, reverse=True)
    return items


def get_citizen_activity(user, profile):
    items = task_activity.get_user_activity(user)
    items.extend(voting_activity.get_user_activity(user))
    for activity in CitizenActivity.objects.filter(uzytkownik=profile).order_by('-timestamp'):
        items.append({'type': 'citizen', 'title': activity.get_activity_type_display(), 'ts': activity.timestamp, 'label': _('Citizenship event'), 'url': None})
    return _sort_activity_items(items)


def get_citizen_created_items(user):
    items = task_activity.get_user_created_items(user)
    items.extend(voting_activity.get_user_created_items(user))
    items.extend(get_user_created_room_items(user))
    return _sort_activity_items(items)
