import asyncio
import logging
import re

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy

from core.richtext import sanitize, strip_tags

from .exceptions import ClientError
from .models import Message, MessageAttachment, Room
from .permissions import get_room_permission_checker
from .serializers import _message_author_labels, _reply_snippet, _username_to_color, build_chat_message_event
from .utils import get_upload_path

log = logging.getLogger(__name__)


def _log_federated_delivery_error(task):
    """Retrieve background delivery exceptions so asyncio does not hide them."""
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        log.exception('Federated message delivery task failed')


SYSTEM_ROOM_DEFINITIONS = {
    'inbox': {
        'title': 'Inbox',
        'is_inbox': True,
        'welcome_message': gettext_lazy('This is where messages from unregistered people outside the group appear. They used the Contact (Send a message to the group) option.'),
    },
    'important': {'title': 'Ważne', 'welcome_message': gettext_lazy('Important documents and announcements appear in this room.')},
}


def ensure_system_rooms():
    """Create or repair the rooms managed by the application."""
    from django.db import IntegrityError, transaction
    from django.db.models import Q

    active_users = User.objects.filter(is_active=True)
    rooms = {}
    for system_key, definition in SYSTEM_ROOM_DEFINITIONS.items():
        try:
            with transaction.atomic():
                room = Room.objects.filter(system_key=system_key).first()
                if room is None:
                    legacy_filter = Q(title=definition['title'])
                    if system_key == 'inbox':
                        legacy_filter |= Q(is_inbox=True)
                    room = Room.objects.filter(legacy_filter).first()
                if room is None:
                    room = Room.objects.create(title=definition['title'], system_key=system_key, public=True, archived=False, protected=True, is_inbox=definition.get('is_inbox', False))
                else:
                    changed_fields = []
                    for field, value in (('system_key', system_key), ('title', definition['title']), ('public', True), ('archived', False), ('protected', True), ('is_inbox', definition.get('is_inbox', False))):
                        if getattr(room, field) != value:
                            setattr(room, field, value)
                            changed_fields.append(field)
                    if changed_fields:
                        room.save(update_fields=changed_fields)

                room.allowed.set(active_users)
                if not room.messages.exists():
                    Message.objects.create(room=room, sender=None, anonymous=False, text=definition['welcome_message'])
                    room.seen_by.set(active_users)
                rooms[system_key] = room
        except IntegrityError:
            # A concurrent post_migrate invocation may have created this room.
            rooms[system_key] = Room.objects.get(system_key=system_key)
    return rooms


# Matches @username in message text; recipient lookup ignores letter case.
_MENTION_RE = re.compile(r'(?<!\w)@([\w@.+-]+)')


def extract_mentions(text: str) -> set:
    """Return set of unique usernames mentioned with @ in the given HTML/text."""
    if not text:
        return set()
    # Normalize <br> tags to spaces so line breaks don't join usernames.
    normalized = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    plain = strip_tags(normalized)
    return set(_MENTION_RE.findall(plain))


def get_user_public_message_rows(user, viewer) -> list[dict]:
    messages = Message.objects.filter(sender=user, room__public=True, anonymous=False).select_related('room').order_by('-time')
    return [{'room': message.room, 'room_name': message.room.displayed_name(viewer), 'msg': message} for message in messages]


def get_user_created_room_items(user) -> list[dict]:
    return [
        {'title': room.displayed_name(user), 'ts': room.last_activity, 'label': gettext_lazy('Chat room'), 'url': reverse('chat:chat') + f'#room_id={room.pk}'}
        for room in Room.objects.filter(founder=user, public=True).order_by('-last_activity')
    ]


def _prepare_message_text(text, linkify=False):
    """Sanitize and normalize raw message text for storage."""
    if text is None:
        text = ''
    message_clean = sanitize(text, linkify=linkify)
    message_clean = re.sub(r'(<br\s*/?>)+$', '', message_clean).rstrip()
    return message_clean


def _is_message_non_empty(text, attachments):
    """Return True if the message has visible content or attachments."""
    return bool(text.strip().replace('<br>', '').replace('<br/>', '') or attachments)


def _can_access_room_sync(room, user):
    """Return True if an authenticated user can read the room."""
    if not room.public:
        return room.allowed.filter(id=user.id).exists()
    return True


def _get_reply_to_data_sync(reply_to_id, room_id, user=None):
    """Return quoted message data from the same room, or raise ClientError."""
    try:
        msg = Message.objects.select_related('room', 'sender').get(pk=reply_to_id)
    except Message.DoesNotExist:
        raise ClientError("MESSAGE_INVALID") from None
    if msg.room_id != room_id:
        raise ClientError("ACCESS_DENIED") from None
    if user is not None and user.is_authenticated and not _can_access_room_sync(msg.room, user):
        raise ClientError("ACCESS_DENIED") from None
    username, display_name = _message_author_labels(msg)
    return {'id': msg.id, 'username': username, 'display_name': display_name, 'text_snippet': _reply_snippet(msg.text), 'author_color': _username_to_color(username)}


def _validate_attachments(attachments):
    """Verify every attachment file exists in MEDIA_ROOT/uploads."""
    for _attachment_type, filenames in attachments.items():
        for filename in filenames:
            path = get_upload_path(filename)
            if not path or not path.is_file():
                raise ClientError("ATTACHMENT_INVALID")


def _save_attachments_sync(message_id, attachments):
    """Persist MessageAttachment rows for a new message."""
    for attachment_type, filenames in attachments.items():
        for filename in filenames:
            MessageAttachment.objects.create(message_id=message_id, type=attachment_type, filename=filename)


def can_user_post_in_room(room, user):
    """Return True if an authenticated user may write in the room."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if not room.public:
        return room.allowed.filter(id=user.id).exists()
    if room.source_object_id:
        checker = get_room_permission_checker(room.source_app)
        if checker is not None:
            return checker(room, user)
    return True


def _create_message(room, sender, text, anonymous, guest_email, guest_name, sender_display_name, reply_to_id, federation_message_id, federation_source_url, federation_source_message_id):
    """Create and save a Message row, returning the instance."""
    message = Message(
        sender=sender,
        text=text,
        room=room,
        anonymous=anonymous,
        guest_email=guest_email,
        guest_name=guest_name,
        sender_display_name=sender_display_name,
        reply_to_id=reply_to_id,
        federation_message_id=federation_message_id or None,
        federation_source_url=federation_source_url or '',
        federation_source_message_id=federation_source_message_id or '',
    )
    message.save()
    return message


def _get_mentioned_users_sync(room, usernames):
    """Return active room members whose username matches a mention."""
    if not usernames:
        return []
    username_filter = Q()
    for username in usernames:
        username_filter |= Q(username__iexact=username)
    return list(room.allowed.filter(username_filter, is_active=True))


def _create_and_build_message(
    room,
    text,
    sender,
    anonymous,
    attachments,
    reply_to_id,
    temp_id,
    guest_email,
    guest_name,
    sender_display_name,
    linkify,
    include_voters,
    federation_message_id,
    federation_source_url,
    federation_source_message_id,
):
    """Sync body of send_message: validate, persist, and build the channel event."""
    message_text = _prepare_message_text(text, linkify=linkify)
    if not _is_message_non_empty(message_text, attachments):
        raise ClientError("MESSAGE_INVALID")

    if not room.public and anonymous:
        raise ClientError("ANONYMOUS_IN_PRIVATE")

    if sender is not None and not can_user_post_in_room(room, sender):
        raise ClientError("ACCESS_DENIED")

    if attachments:
        _validate_attachments(attachments)

    reply_to = None
    if reply_to_id:
        reply_to = _get_reply_to_data_sync(reply_to_id, room.id, user=sender)

    message = _create_message(room, sender, message_text, anonymous, guest_email, guest_name, sender_display_name, reply_to_id, federation_message_id, federation_source_url, federation_source_message_id)

    if sender is not None:
        Room.enable_notifications_after_message(room.id, sender.id)

    if attachments:
        _save_attachments_sync(message.id, attachments)

    mentioned_usernames = extract_mentions(message_text)
    mentioned_users = _get_mentioned_users_sync(room, mentioned_usernames)

    event = build_chat_message_event(message, new=True, temp_id=temp_id, include_voters=include_voters, reply_to=reply_to)

    return message, event, mentioned_users


async def send_message(
    room,
    text,
    sender=None,
    *,
    anonymous=True,
    attachments=None,
    reply_to_id=None,
    temp_id=None,
    guest_email='',
    guest_name='',
    sender_display_name='',
    linkify=False,
    include_voters=False,
    channel_layer=None,
    online_registry=None,
    background=False,
    federation_message_id='',
    federation_source_url='',
    federation_source_message_id='',
    propagate_federated=True,
    push_event=None,
    notify_members=True,
):
    """Create a chat message, broadcast it, and dispatch notifications.

    Single service used by WebSocket consumer, REST views, and signals.
    """
    if channel_layer is None:
        channel_layer = get_channel_layer()
    if online_registry is None:
        from .consumers import ChatConsumer

        online_registry = ChatConsumer.online_registry

    attachments = attachments or {}

    message, event, mentioned_users = await database_sync_to_async(_create_and_build_message)(
        room=room,
        text=text,
        sender=sender,
        anonymous=anonymous,
        attachments=attachments,
        reply_to_id=reply_to_id,
        temp_id=temp_id,
        guest_email=guest_email,
        guest_name=guest_name,
        sender_display_name=sender_display_name,
        linkify=linkify,
        include_voters=include_voters,
        federation_message_id=federation_message_id,
        federation_source_url=federation_source_url,
        federation_source_message_id=federation_source_message_id,
    )

    await channel_layer.group_send(room.group_name, event)

    from .notifications import ChatNotificationService

    await ChatNotificationService(channel_layer, online_registry).dispatch_message(room, message, sender, mentioned_users, push_event=push_event, notify_members=notify_members)
    if propagate_federated and room.federated_instance_url:
        from .federation import deliver_message

        delivery_task = asyncio.create_task(deliver_message(room, message))
        delivery_task.add_done_callback(_log_federated_delivery_error)
    return message
