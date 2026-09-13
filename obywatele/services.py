from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from django.utils.translation import gettext as _

from chat.models import Room
from chat.services import ensure_system_rooms, get_user_created_room_items, send_message
from glosowania import activity as voting_activity
from tasks import activity as task_activity

from .models import CitizenActivity


def publish_deletion_feedback(reason, *, anonymous, author_name=''):
    """Publish an account-deletion opinion in the shared Inbox."""
    inbox = Room.objects.filter(system_key='inbox', public=True).first()
    if inbox is None:
        inbox = ensure_system_rooms().get('inbox')
    if inbox is None or not inbox.public:
        raise RuntimeError('The Inbox room is unavailable.')

    author_label = _('Former group member') if anonymous else author_name
    message_text = _('Account-deletion feedback from a former group member. This message was published because its author chose to share it.\n\n%(reason)s') % {'reason': reason}
    async_to_sync(send_message)(inbox, message_text, sender=None, anonymous=anonymous, sender_display_name=author_label, linkify=True)


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
