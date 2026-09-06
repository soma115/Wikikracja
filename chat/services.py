import asyncio
import logging
import re
import uuid

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.db.models import Count, Prefetch
from django.utils.translation import gettext as _

from zzz.notifications import NOTIF_LOG_TAG
from zzz.richtext import sanitize, strip_tags
from zzz.templatetags.citizen_filters import citizen_color_class
from zzz.utils import get_site_domain

from .exceptions import ClientError
from .models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy, Room
from .utils import get_upload_path

log = logging.getLogger(__name__)

CHAT_UNREAD_CACHE_KEY = "chat_unread:{user_id}"
CHAT_UNREAD_CACHE_TTL = 300

# Matches @username in message text. User must type the exact nickname; no autocomplete.
_MENTION_RE = re.compile(r'(?<!\w)@([\w@.+-]+)')


def extract_mentions(text: str) -> set:
    """Return set of unique usernames mentioned with @ in the given HTML/text."""
    if not text:
        return set()
    # Normalize <br> tags to spaces so line breaks don't join usernames.
    normalized = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    plain = strip_tags(normalized)
    return set(_MENTION_RE.findall(plain))


def _reply_snippet(text: str, max_len: int = 240) -> str:
    """Plain-text snippet for quoted message; strips HTML and expandable hint."""
    if not text:
        return ''
    plain = strip_tags(text)
    plain = plain.replace('… pokaż więcej', '').strip()
    return plain[:max_len]


def get_unread_count_for_user(user) -> int:
    key = CHAT_UNREAD_CACHE_KEY.format(user_id=user.id)
    cached = cache.get(key)
    if cached is not None:
        return cached
    count = Room.objects.filter(allowed=user, archived=False, is_inbox=False).exclude(seen_by=user).annotate(messages_count=Count('messages')).filter(messages_count__gt=0).count()
    cache.set(key, count, CHAT_UNREAD_CACHE_TTL)
    return count


def _reactions(message) -> dict:
    return message.reactions if isinstance(message.reactions, dict) else {}


def _voter_names_by_id(user_ids) -> dict:
    """Return {user_id: username} for the given ids (skips deleted users)."""
    if not user_ids:
        return {}
    return dict(User.objects.filter(id__in=user_ids).values_list('id', 'username'))


def _voter_lists(reactions_dict: dict, names_by_id: dict) -> dict:
    """Map vote id-lists in reactions to usernames: {'upvoters': [...], 'downvoters': [...]}."""
    return {
        'upvoters': [names_by_id[uid] for uid in reactions_dict.get('upvotes', []) if uid in names_by_id],
        'downvoters': [names_by_id[uid] for uid in reactions_dict.get('downvotes', []) if uid in names_by_id],
    }


def _username_to_color(username: str) -> str:
    """Deterministic hex color for username (for quote border-left)."""
    hue = sum(ord(c) for c in username) % 360
    return f"hsl({hue}, 60%, 55%)"


def get_avatar_url(user):
    """Get user's uploaded avatar URL, or None when user has no avatar.

    Callers decide the fallback (placeholder image, initials, etc.).
    """
    try:
        profile = user.uzytkownik
        if profile.avatar:
            return profile.avatar.url
    except Exception:
        pass
    return None


def build_chat_message_event(message: Message, *, new: bool = False, temp_id: str = None, include_voters: bool = False, read_by=None, voter_names=None, reply_to=None) -> dict:
    """Build the transport event for a chat message.

    Single source of truth for the shape of a `chat.message` channel event
    and for the data returned by `get_recent_messages_batch`.
    """
    reactions_dict = _reactions(message)

    upvotes = getattr(message, 'upvotes', None)
    if upvotes is None:
        upvotes = len(reactions_dict.get('upvotes', []))
    downvotes = getattr(message, 'downvotes', None)
    if downvotes is None:
        downvotes = len(reactions_dict.get('downvotes', []))

    attachments = {}
    for attachment in message.attachments.all():
        attachments.setdefault(attachment.type, []).append(attachment.filename)

    reply_to_data = reply_to
    if reply_to_data is None and message.reply_to_id and message.reply_to:
        rm = message.reply_to
        ru = 'System' if rm.sender is None else ('Anonymous' if rm.anonymous else rm.sender.username)
        reply_to_data = {'id': rm.id, 'username': ru, 'text_snippet': _reply_snippet(rm.text), 'author_color': _username_to_color(ru)}

    read_by_data = []
    if read_by:
        for entry in read_by:
            u = entry.user
            read_by_data.append({'user_id': u.id, 'username': u.username, 'avatar_url': get_avatar_url(u) or '/static/home/images/favicon.ico', 'citizen_color_class': citizen_color_class(u.username)})

    event = {
        'type': 'chat.message',
        'room_id': message.room_id,
        'user_id': message.sender_id,
        'message_id': message.id,
        'message': message.text,
        'anonymous': message.anonymous,
        'upvotes': upvotes,
        'downvotes': downvotes,
        'new': new,
        'edited': hasattr(message, 'messagehistory'),
        'timestamp': int(message.time.timestamp()) * 1000,
        'latest_timestamp': int(message.time.timestamp()) * 1000,
        'attachments': attachments,
        'reply_to': reply_to_data,
        'reactions': {'bulb': len(reactions_dict.get('bulb', [])), 'question': len(reactions_dict.get('question', []))},
        'read_by': read_by_data,
        'temp_id': temp_id,
    }

    if include_voters:
        if voter_names is None:
            voter_ids = set(reactions_dict.get('upvotes', [])) | set(reactions_dict.get('downvotes', []))
            voter_names = _voter_names_by_id(voter_ids)
        event.update(_voter_lists(reactions_dict, voter_names))

    return event


class ChatRepository:
    def __init__(self, user):
        self.user = user

    def _ensure_room_access(self, room):
        if not self.user.is_authenticated:
            raise ClientError("USER_HAS_TO_LOGIN")
        if not room.public and not room.allowed.filter(id=self.user.id).exists():
            raise ClientError("ACCESS_DENIED")

    def _get_accessible_room(self, room_id):
        try:
            room = Room.objects.get(pk=room_id)
        except Room.DoesNotExist:
            raise ClientError("ROOM_INVALID") from None
        self._ensure_room_access(room)
        return room

    def _get_accessible_message(self, message_id, room_id=None):
        try:
            message = Message.objects.select_related('room').get(pk=message_id)
        except Message.DoesNotExist:
            raise ClientError("MESSAGE_INVALID") from None
        if room_id is not None and message.room_id != room_id:
            raise ClientError("ACCESS_DENIED")
        self._ensure_room_access(message.room)
        return message

    # -- Room methods --
    @database_sync_to_async
    def get_room_or_error(self, room_id):
        """Tries to fetch a room for the user, checking permissions along the way."""
        return self._get_accessible_room(room_id)

    @database_sync_to_async
    def find_rooms_with(self, *users):
        """Find private 1 to 1 room with given users"""
        return list(Room.find_all_with_users(*users))

    @database_sync_to_async
    def find_private_rooms_for_user_pairs(self, user, other_user_ids):
        """Optimized batch version: Find all private 1-to-1 rooms between the given user and multiple other users."""
        return Room.find_private_rooms_for_user_pairs(user, other_user_ids)

    @database_sync_to_async
    def has_muted_room(self, room_id):
        room = self._get_accessible_room(room_id)
        return Room.muted_by.through.objects.filter(room_id=room.id, user_id=self.user.id).exists()

    @database_sync_to_async
    def user_has_muted_room(self, user_id, room_id):
        return Room.muted_by.through.objects.filter(room_id=room_id, user_id=user_id).exists()

    @database_sync_to_async
    def unmute_room(self, room_id):
        self._get_accessible_room(room_id).muted_by.remove(self.user)

    @database_sync_to_async
    def mute_room(self, room_id):
        room = self._get_accessible_room(room_id)
        if not room.muted_by.filter(id=self.user.id).exists():
            room.muted_by.add(self.user)

    @database_sync_to_async
    def get_rooms_with_notifications_enabled(self):
        """Returns list of rooms where user is allowed and not muted."""
        return list(Room.objects.filter(allowed=self.user).exclude(muted_by=self.user))

    @database_sync_to_async
    def can_post_in_room(self, room):
        """Return True if the current user may write in the given room."""
        return _can_post_in_room(room, self.user)

    @database_sync_to_async
    def room_is_seen(self, room):
        return room.messages.all().count() == 0 or self.user.seen_rooms.filter(id=room.id).exists()

    @database_sync_to_async
    def see_room(self, room):
        room.seen_by.add(self.user)
        cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=self.user.id))

    @database_sync_to_async
    def unsee_room(self, room):
        room.seen_by.remove(self.user)
        cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=self.user.id))

    @database_sync_to_async
    def get_unread_count(self) -> int:
        return get_unread_count_for_user(self.user)

    # -- User methods --
    @database_sync_to_async
    def get_user_by_id(self, id):
        if id is None:
            log.debug("Attempted to fetch user with ID None; returning None")
            return None
        try:
            return User.objects.select_related('uzytkownik').get(id=id)
        except User.DoesNotExist:
            log.error(f"User with ID {id} does not exist")
            return None

    # -- Message methods --
    @database_sync_to_async
    def get_message(self, message_id):
        return self._get_accessible_message(message_id)

    @database_sync_to_async
    def get_message_sender(self, message):
        if isinstance(message, (int, str)):
            return self._get_accessible_message(message).sender
        return message.sender

    @database_sync_to_async
    def get_room_by_message(self, message_id: int):
        return self._get_accessible_message(message_id).room

    @database_sync_to_async
    def edit_message_and_history(self, message_id: int, new_message: str):
        """Save current message state as old and update message text"""
        message = self._get_accessible_message(message_id)
        msg_history, created = MessageHistory.objects.get_or_create(message=message)
        state = MessageHistoryEntry.objects.create(history=msg_history, text=message.text)
        message.text = new_message
        message.save(update_fields=('text',))
        return state

    @database_sync_to_async
    def is_last_message_in_room(self, message_id: int, room_id: int) -> bool:
        return not Message.objects.filter(room_id=room_id, pk__gt=message_id).exists()

    @database_sync_to_async
    def get_message_states(self, message_id):
        self._get_accessible_message(message_id)
        history = MessageHistory.objects.filter(message_id=message_id)
        if not history.exists():
            return []
        history = history.first()
        states = [{"text": state.text, "timestamp": int(state.time.timestamp()) * 1000} for state in history.entries.all().order_by("time")]
        return states

    # -- Attachment methods --
    @database_sync_to_async
    def save_attachments(self, message_id, attachments):
        for attachment_type, filenames in attachments.items():
            for filename in filenames:
                MessageAttachment.objects.create(message_id=message_id, type=attachment_type, filename=filename)

    @database_sync_to_async
    def load_attachments(self, message_id):
        attachments = {}
        for attachment in MessageAttachment.objects.filter(message_id=message_id):
            attachments_of_type = attachments.get(attachment.type, [])
            attachments_of_type.append(attachment.filename)
            attachments[attachment.type] = attachments_of_type
        return attachments

    @database_sync_to_async
    def remove_attachments(self, message_id, filenames):
        for filename in filenames:
            MessageAttachment.objects.filter(message_id=message_id, filename=filename).delete()

    # -- Vote methods --
    @database_sync_to_async
    def add_vote(self, event: str, message_id: int):
        """Add a vote directly to the message's reactions JSONField."""
        m = self._get_accessible_message(message_id)
        reactions_dict = _reactions(m)
        user_id = self.user.id

        if 'upvotes' not in reactions_dict:
            reactions_dict['upvotes'] = []
        if 'downvotes' not in reactions_dict:
            reactions_dict['downvotes'] = []

        if user_id in reactions_dict['upvotes']:
            reactions_dict['upvotes'].remove(user_id)
        if user_id in reactions_dict['downvotes']:
            reactions_dict['downvotes'].remove(user_id)

        if event == 'upvote':
            reactions_dict['upvotes'].append(user_id)
        else:
            reactions_dict['downvotes'].append(user_id)

        m.reactions = reactions_dict
        m.save(update_fields=['reactions'])

        return len(reactions_dict.get('upvotes', [])), len(reactions_dict.get('downvotes', []))

    @database_sync_to_async
    def remove_vote(self, event: str, message_id: int):
        """Remove a vote directly from the message's reactions JSONField."""
        m = self._get_accessible_message(message_id)
        reactions_dict = _reactions(m)
        user_id = self.user.id

        if event == 'upvote' and user_id in reactions_dict.get('upvotes', []):
            reactions_dict['upvotes'].remove(user_id)
        elif event == 'downvote' and user_id in reactions_dict.get('downvotes', []):
            reactions_dict['downvotes'].remove(user_id)

        m.reactions = reactions_dict
        m.save(update_fields=['reactions'])

        return len(reactions_dict.get('upvotes', [])), len(reactions_dict.get('downvotes', []))

    @database_sync_to_async
    def get_vote(self, message_id: int):
        """Check the reactions JSONField on the message."""
        try:
            m = self._get_accessible_message(message_id)
        except ClientError as e:
            if e.code == "MESSAGE_INVALID":
                return None
            raise
        reactions_dict = _reactions(m)
        user_id = self.user.id

        if user_id in reactions_dict.get('upvotes', []):
            return type('Vote', (), {'vote': 'upvote'})()
        elif user_id in reactions_dict.get('downvotes', []):
            return type('Vote', (), {'vote': 'downvote'})()
        return None

    @database_sync_to_async
    def get_vote_voters(self, message_id: int) -> dict:
        """Return {'upvoters': [usernames], 'downvoters': [usernames]} for a message.

        Used in task rooms (source_app == 'tasks'), where votes are public.
        """
        try:
            m = self._get_accessible_message(message_id)
        except ClientError as e:
            if e.code == "MESSAGE_INVALID":
                return {'upvoters': [], 'downvoters': []}
            raise
        r = _reactions(m)
        names = _voter_names_by_id(set(r.get('upvotes', [])) | set(r.get('downvotes', [])))
        return _voter_lists(r, names)

    # -- Reaction methods --
    @database_sync_to_async
    def toggle_reaction(self, reaction: str, message_id: int) -> bool:
        """Toggle reaction for current user. Returns True if added, False if removed."""
        m = self._get_accessible_message(message_id)
        reactions_dict = _reactions(m)
        user_id = self.user.id

        if reaction not in reactions_dict:
            reactions_dict[reaction] = []

        if user_id in reactions_dict[reaction]:
            reactions_dict[reaction].remove(user_id)
            added = False
        else:
            reactions_dict[reaction].append(user_id)
            added = True

        m.reactions = reactions_dict
        m.save(update_fields=['reactions'])
        return added

    @database_sync_to_async
    def get_reaction_counts(self, message_id: int) -> dict:
        """Return {reaction: count} for message."""
        try:
            m = self._get_accessible_message(message_id)
        except ClientError as e:
            if e.code == "MESSAGE_INVALID":
                return {'bulb': 0, 'question': 0}
            raise

        reactions_dict = _reactions(m)
        return {'bulb': len(reactions_dict.get('bulb', [])), 'question': len(reactions_dict.get('question', []))}

    @database_sync_to_async
    def get_user_reactions(self, user_id: int, message_id: int) -> list:
        """Return list of reactions for user on message."""
        try:
            m = self._get_accessible_message(message_id)
        except ClientError as e:
            if e.code == "MESSAGE_INVALID":
                return []
            raise

        reactions_dict = _reactions(m)
        result = []
        for reaction_type, user_list in reactions_dict.items():
            if reaction_type in ('bulb', 'question') and user_id in user_list:
                result.append(reaction_type)
        return result

    # -- Read by methods --
    @database_sync_to_async
    def mark_message_read(self, message_id: int):
        """Mark message as read by current user."""
        message = self._get_accessible_message(message_id)
        MessageReadBy.objects.get_or_create(message=message, user=self.user)

    @database_sync_to_async
    def mark_messages_read_bulk(self, message_ids: list, room_id: int) -> list:
        """Mark multiple messages read in one accessible room; return newly created ids."""
        room = self._get_accessible_room(room_id)
        try:
            requested_ids = set(int(message_id) for message_id in message_ids)
        except (TypeError, ValueError):
            raise ClientError("MESSAGE_INVALID") from None
        room_message_ids = set(Message.objects.filter(room=room, id__in=requested_ids).values_list('id', flat=True))
        if room_message_ids != requested_ids:
            raise ClientError("ACCESS_DENIED")
        existing = set(MessageReadBy.objects.filter(message_id__in=requested_ids, user=self.user).values_list('message_id', flat=True))
        new_ids = requested_ids - existing
        if new_ids:
            MessageReadBy.objects.bulk_create([MessageReadBy(message_id=mid, user=self.user) for mid in new_ids], ignore_conflicts=True)
        return list(new_ids)

    @database_sync_to_async
    def get_read_by_data(self, message_id: int) -> list:
        """Return list of {user_id, username, avatar_url} for message."""
        message = self._get_accessible_message(message_id)
        entries = MessageReadBy.objects.filter(message=message).select_related('user__uzytkownik').order_by('id')[:10]
        result = []
        for entry in entries:
            user = entry.user
            avatar_url = get_avatar_url(user) or "/static/home/images/favicon.ico"
            result.append({'user_id': user.id, 'username': user.username, 'avatar_url': avatar_url, 'citizen_color_class': citizen_color_class(user.username)})
        return result

    # -- Recent messages methods --
    @database_sync_to_async
    def get_recent_messages_batch(self, room_id, user_id, limit=100, sort_by='date', order='desc', popular_only=False, include_voters=False):
        qs = Message.objects.filter(room=room_id).select_related('sender', 'reply_to__sender').prefetch_related(Prefetch('attachments', queryset=MessageAttachment.objects.all()), 'messagehistory')

        if sort_by == 'date' and not popular_only:
            # Fast path: DB handles ORDER BY + LIMIT using the (room, time) index
            db_order = 'time' if order == 'asc' else '-time'
            messages = list(qs.order_by(db_order)[:limit])
            if order == 'desc':
                messages = list(reversed(messages))
            for msg in messages:
                r = _reactions(msg)
                msg.upvotes = len(r.get('upvotes', []))
                msg.downvotes = len(r.get('downvotes', []))
        else:
            # Python path: full scan needed to filter/sort by reactions (stored in JSONField)
            all_messages = list(qs)
            for msg in all_messages:
                r = _reactions(msg)
                msg.upvotes = len(r.get('upvotes', []))
                msg.downvotes = len(r.get('downvotes', []))

            if popular_only:
                all_messages = [msg for msg in all_messages if msg.upvotes >= 1]

            reverse = order == 'desc'
            if sort_by == 'likes':
                all_messages.sort(key=lambda m: (m.upvotes, m.time), reverse=reverse)
            else:
                all_messages.sort(key=lambda m: m.time, reverse=reverse)

            messages = all_messages[:limit]
            if sort_by == 'date' and order == 'desc':
                messages = list(reversed(messages))

        if not messages:
            return {'messages': [], 'users': {}, 'user_votes': {}}

        sender_ids = {msg.sender_id for msg in messages if msg.sender_id}
        users = {u.id: u for u in User.objects.filter(id__in=sender_ids).select_related('uzytkownik')} if sender_ids else {}

        message_ids = [msg.id for msg in messages]
        read_by_qs = MessageReadBy.objects.filter(message_id__in=message_ids).select_related('user__uzytkownik').order_by('id')
        read_by_map = {}
        for entry in read_by_qs:
            read_by_map.setdefault(entry.message_id, []).append(entry)
        for mid, entries in read_by_map.items():
            read_by_map[mid] = entries[:10]

        user_votes = {}
        for msg in messages:
            r = _reactions(msg)
            if user_id in r.get('upvotes', []):
                user_votes[msg.id] = 'upvote'
            elif user_id in r.get('downvotes', []):
                user_votes[msg.id] = 'downvote'

        voter_names = {}
        if include_voters:
            voter_ids = set()
            for msg in messages:
                r = _reactions(msg)
                voter_ids.update(r.get('upvotes', []), r.get('downvotes', []))
            voter_names = _voter_names_by_id(voter_ids)

        result = [build_chat_message_event(msg, new=False, include_voters=include_voters, read_by=read_by_map.get(msg.id, []), voter_names=voter_names) for msg in messages]

        return {'messages': result, 'users': users, 'user_votes': user_votes}

    # -- Push notification methods --
    @database_sync_to_async
    def send_push_notification_sync(self, user, title, body, deep_link, room_id, room_name=""):
        """Synchronous push notification sending via the shared notifications backend."""
        try:
            from zzz.notifications import NOTIF_LOG_TAG, build_notification, send_fcm_to_user_sync

            notification = build_notification(title, body, deep_link, f"chat-{room_id}", room_id=room_id, room_name=room_name)
            return send_fcm_to_user_sync(user, notification, notification_type='chat')
        except Exception as e:
            log.error(f"{NOTIF_LOG_TAG} Error in send_push_notification_sync: {e}", exc_info=True)
            return False


def _room_notification_name(room, sender):
    """Room name to display in notifications: public room title, private chat = sender."""
    return room.title if room.public else (sender.username if sender else "System")


async def _build_chat_notification(author, room_id, room_name=None):
    """Build the title/body/icon/click_action shared by WS and FCM chat notifications."""
    site_url = f"https://{await database_sync_to_async(get_site_domain)()}"
    notification_id = uuid.uuid4().hex
    log.debug(f"{NOTIF_LOG_TAG} Built chat notification {notification_id} for room {room_id} (author={author})")
    return {
        'notification_id': notification_id,
        'title': _("Room: %(room)s") % {'room': room_name} if room_name else _("Chat"),
        'body': _("Sender: %(author)s") % {'author': author},
        'icon': f"{site_url}/favicon.ico",
        'click_action': f"{site_url}/chat#room_id={room_id}",
    }


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
    username = 'System' if msg.sender is None else ('Anonymous' if msg.anonymous else msg.sender.username)
    return {'id': msg.id, 'username': username, 'text_snippet': _reply_snippet(msg.text), 'author_color': _username_to_color(username)}


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


def _can_post_in_room(room, user):
    """Return True if an authenticated user may write in the room."""
    if not user or not user.is_authenticated:
        return False
    if not room.public:
        return room.allowed.filter(id=user.id).exists()
    if room.source_app == 'tasks' and room.source_object_id:
        from tasks.models import Task

        try:
            task = Task.objects.get(pk=room.source_object_id)
        except Task.DoesNotExist:
            return True
        return task.can_user_post(user)
    return True


def _create_message(room, sender, text, anonymous, guest_email, guest_name, reply_to_id):
    """Create and save a Message row, returning the instance."""
    message = Message(sender=sender, text=text, room=room, anonymous=anonymous, guest_email=guest_email, guest_name=guest_name, reply_to_id=reply_to_id)
    message.save()
    return message


def _get_mentioned_users_sync(room, usernames):
    """Return active room members whose username is in usernames."""
    if not usernames:
        return []
    return list(room.allowed.filter(username__in=usernames, is_active=True))


def _create_and_build_message(room, text, sender, anonymous, attachments, reply_to_id, temp_id, guest_email, guest_name, linkify, include_voters):
    """Sync body of send_message: validate, persist, and build the channel event."""
    message_text = _prepare_message_text(text, linkify=linkify)
    if not _is_message_non_empty(message_text, attachments):
        raise ClientError("MESSAGE_INVALID")

    if not room.public and anonymous:
        raise ClientError("ANONYMOUS_IN_PRIVATE")

    if sender is not None and not _can_post_in_room(room, sender):
        raise ClientError("ACCESS_DENIED")

    if attachments:
        _validate_attachments(attachments)

    reply_to = None
    if reply_to_id:
        reply_to = _get_reply_to_data_sync(reply_to_id, room.id, user=sender)

    message = _create_message(room, sender, message_text, anonymous, guest_email, guest_name, reply_to_id)

    if attachments:
        _save_attachments_sync(message.id, attachments)

    mentioned_usernames = extract_mentions(message_text)
    mentioned_users = _get_mentioned_users_sync(room, mentioned_usernames)

    event = build_chat_message_event(message, new=True, temp_id=temp_id, include_voters=include_voters, reply_to=reply_to)

    return message, event, mentioned_users


async def _dispatch_message_notifications(channel_layer, room, message, sender, event, mentioned_users, online_registry, *, background=False):
    """Notify recipients after a message has been broadcast.

    Handles unread state for offline users, WebSocket notifications for online
    users, and both push + channel mention events for explicitly mentioned users.

    When ``background=True`` (WebSocket consumer), push/mention work is scheduled
    as fire-and-forget tasks so the consumer can return immediately.  When
    ``background=False`` (REST views / signals), all work is awaited so that
    ``async_to_sync`` callers do not kill the event loop before pushes finish.
    """
    try:
        mentioned_user_ids = {u.id for u in mentioned_users}
        room_members = await database_sync_to_async(lambda: list(room.allowed.all()))()
        other_members = [m for m in room_members if m.id != (sender.id if sender else None)]
        if not other_members:
            return

        other_member_ids = [m.id for m in other_members]

        online_ids = set(online_registry.get_online())
        offline_ids = [mid for mid in other_member_ids if mid not in online_ids]
        if offline_ids:
            await database_sync_to_async(lambda: Room.seen_by.through.objects.filter(room_id=room.id, user_id__in=offline_ids).delete())()
            await database_sync_to_async(lambda: cache.delete_many([CHAT_UNREAD_CACHE_KEY.format(user_id=uid) for uid in offline_ids]))()

        membership_prefs = await database_sync_to_async(Room.get_membership_preferences_bulk)(room.id, other_member_ids)

        author = "Anonymous" if message.anonymous else (sender.username if sender else "System")
        notify_room_name = _room_notification_name(room, sender)
        notification = await _build_chat_notification(author, room.id, notify_room_name)

        for member in other_members:
            prefs = membership_prefs.get(member.id, {'seen': False, 'muted': True})
            consumer = online_registry.get_consumer(member)
            is_present = bool(consumer) and consumer.rooms.present(room)
            is_mentioned = member.id in mentioned_user_ids

            if not prefs['muted'] and not is_mentioned:
                if background:
                    asyncio.create_task(_send_push_to_user(member, message, room, notify_room_name))
                else:
                    await _send_push_to_user(member, message, room, notify_room_name)
                log.debug(f"{NOTIF_LOG_TAG} group_send chat.notification notification_id={notification['notification_id']} to user_{member.id} for message {message.id} (present={is_present})")
                await channel_layer.group_send(f"user_{member.id}", {"type": "chat.notification", "room_id": room.id, "notification": {**notification, "room_id": room.id}})

            if consumer and not is_present and prefs['seen']:
                await consumer.repo.unsee_room(room)
                await consumer.push_unread_count()
                await consumer.send_json({"unsee_room": room.id})

        if mentioned_users:
            for user in mentioned_users:
                if user.id == (sender.id if sender else None):
                    continue
                if background:
                    asyncio.create_task(_send_mention(channel_layer, room, message, user, notify_room_name, online_registry))
                else:
                    await _send_mention(channel_layer, room, message, user, notify_room_name, online_registry)
    except Exception as e:
        log.error(f"{NOTIF_LOG_TAG} Error in dispatch_message_notifications for message {message.id}: {e}", exc_info=True)


async def _send_push_to_user(user, message, room, room_name):
    """Send a single push notification via ChatRepository."""
    try:
        author = "Anonymous" if message.anonymous else (message.sender.username if message.sender else "System")
        notification = await _build_chat_notification(author, room.id, room_name)
        repo = ChatRepository(AnonymousUser())
        success = await repo.send_push_notification_sync(user, notification['title'], notification['body'], notification['click_action'], room.id, room_name=room_name)
        if success:
            log.info(f"{NOTIF_LOG_TAG} Push notification sent to user {user.id} for message {message.id} (ws notification_id={notification['notification_id']})")
        else:
            log.debug(f"{NOTIF_LOG_TAG} No push devices active for user {user.id} (ws notification_id={notification['notification_id']})")
    except Exception as e:
        log.error(f"{NOTIF_LOG_TAG} Error sending push notification to user {user.id}: {e}", exc_info=True)


async def _send_mention(channel_layer, room, message, user, room_name, online_registry):
    """Send a WebSocket mention event and a push for a single mention."""
    try:
        author = "Anonymous" if message.anonymous else (message.sender.username if message.sender else "System")
        notification = await _build_chat_notification(author, room.id, room_name)

        log.debug(f"{NOTIF_LOG_TAG} group_send chat.mention notification_id={notification['notification_id']} to user_{user.id} for message {message.id}")
        await channel_layer.group_send(f"user_{user.id}", {"type": "chat.mention", "room_id": room.id, "notification": {**notification, "room_id": room.id}})

        repo = ChatRepository(AnonymousUser())
        success = await repo.send_push_notification_sync(user, notification['title'], notification['body'], notification['click_action'], room.id, room_name=room_name)
        if success:
            log.info(f"{NOTIF_LOG_TAG} Mention notification sent to user {user.id} for message {message.id} (ws notification_id={notification['notification_id']})")
        else:
            log.debug(f"{NOTIF_LOG_TAG} No push devices active for mention to user {user.id} (ws notification_id={notification['notification_id']})")
    except Exception as e:
        log.error(f"{NOTIF_LOG_TAG} Error sending mention notification to user {user.id}: {e}", exc_info=True)


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
    linkify=False,
    include_voters=False,
    channel_layer=None,
    online_registry=None,
    background=False,
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
        linkify=linkify,
        include_voters=include_voters,
    )

    await channel_layer.group_send(room.group_name, event)

    if background:
        asyncio.create_task(_dispatch_message_notifications(channel_layer, room, message, sender, event, mentioned_users, online_registry, background=True))
    else:
        await _dispatch_message_notifications(channel_layer, room, message, sender, event, mentioned_users, online_registry, background=False)

    return message
