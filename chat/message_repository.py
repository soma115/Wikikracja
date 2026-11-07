import logging

from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.db.models import Prefetch, Q

from .models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy
from .reactions import _reactions, _voter_names_by_id
from .room_repository import ChatRoomRepository
from .serializers import build_chat_message_event

log = logging.getLogger(__name__)


class ChatMessageRepository:
    """Persist and retrieve messages, their edit history, and attachments."""

    def __init__(self, user, room_repository=None):
        self.user = user
        self.room_repository = room_repository or ChatRoomRepository(user)

    def get_accessible_message_sync(self, message_id, room_id=None):
        return self.room_repository.get_accessible_message_sync(message_id, room_id)

    @database_sync_to_async
    def get_message(self, message_id):
        return self.get_accessible_message_sync(message_id)

    @database_sync_to_async
    def get_user_by_id(self, user_id):
        if user_id is None:
            log.debug("Attempted to fetch user with ID None; returning None")
            return None
        try:
            return User.objects.select_related('uzytkownik').get(id=user_id)
        except User.DoesNotExist:
            log.error(f"User with ID {user_id} does not exist")
            return None

    @database_sync_to_async
    def get_message_sender(self, message):
        if isinstance(message, (int, str)):
            return self.get_accessible_message_sync(message).sender
        return message.sender

    @database_sync_to_async
    def get_room_by_message(self, message_id: int):
        return self.get_accessible_message_sync(message_id).room

    @database_sync_to_async
    def edit_message_and_history(self, message_id: int, new_message: str):
        """Save current message state as old and update message text."""
        message = self.get_accessible_message_sync(message_id)
        msg_history, _ = MessageHistory.objects.get_or_create(message=message)
        state = MessageHistoryEntry.objects.create(history=msg_history, text=message.text)
        message.text = new_message
        message.save(update_fields=('text',))
        return state

    @database_sync_to_async
    def is_last_message_in_room(self, message_id: int, room_id: int) -> bool:
        return not Message.objects.filter(room_id=room_id, pk__gt=message_id).exists()

    @database_sync_to_async
    def get_message_states(self, message_id):
        self.get_accessible_message_sync(message_id)
        history = MessageHistory.objects.filter(message_id=message_id)
        if not history.exists():
            return []
        history = history.first()
        return [{"text": state.text, "timestamp": int(state.time.timestamp()) * 1000} for state in history.entries.all().order_by("time")]

    @database_sync_to_async
    def get_recent_messages_batch(self, room_id, limit=100, sort_by='date', order='desc', popular_only=False, include_voters=False, target_message_id=None):
        qs = Message.objects.filter(room=room_id).select_related('sender', 'reply_to__sender').prefetch_related(Prefetch('attachments', queryset=MessageAttachment.objects.all()), 'messagehistory')

        if sort_by is None and not popular_only:
            messages = list(qs[:limit])
        elif sort_by == 'date' and not popular_only:
            # Fast path: DB handles ORDER BY + LIMIT using the (room, time) index
            db_order = 'time' if order == 'asc' else '-time'
            db_id_order = 'id' if order == 'asc' else '-id'
            target = qs.filter(pk=target_message_id).first() if target_message_id is not None else None
            if target is None:
                messages = list(qs.order_by(db_order, db_id_order)[:limit])
                if order == 'desc':
                    messages = list(reversed(messages))
            else:
                before_query = Q(time__lt=target.time) | Q(time=target.time, pk__lt=target.pk)
                after_query = Q(time__gt=target.time) | Q(time=target.time, pk__gt=target.pk)
                before_query_set = qs.filter(before_query).order_by('-time', '-id')
                after_query_set = qs.filter(after_query).order_by('time', 'id')
                before_limit = limit // 2
                after_limit = limit - before_limit - 1
                before = list(before_query_set[:before_limit])
                after = list(after_query_set[:after_limit])
                if len(before) < before_limit:
                    after = list(after_query_set[: after_limit + before_limit - len(before)])
                elif len(after) < after_limit:
                    before = list(before_query_set[: before_limit + after_limit - len(after)])
                messages = [*reversed(before), target, *after]
            for message in messages:
                reactions = _reactions(message)
                message.upvotes = len(reactions.get('upvotes', []))
                message.downvotes = len(reactions.get('downvotes', []))
        else:
            # Python path: full scan needed to filter/sort by reactions (stored in JSONField)
            all_messages = list(qs)
            for message in all_messages:
                reactions = _reactions(message)
                message.upvotes = len(reactions.get('upvotes', []))
                message.downvotes = len(reactions.get('downvotes', []))

            if popular_only:
                all_messages = [message for message in all_messages if message.upvotes >= 1]

            if sort_by is not None:
                reverse = order == 'desc'
                if sort_by == 'likes':
                    all_messages.sort(key=lambda message: (message.upvotes, message.time), reverse=reverse)
                else:
                    all_messages.sort(key=lambda message: message.time, reverse=reverse)

            messages = all_messages[:limit]
            if sort_by == 'date' and order == 'desc':
                messages = list(reversed(messages))

        if not messages:
            return {'messages': [], 'users': {}, 'user_votes': {}}

        sender_ids = {message.sender_id for message in messages if message.sender_id}
        users = {user.id: user for user in User.objects.filter(id__in=sender_ids).select_related('uzytkownik')} if sender_ids else {}

        message_ids = [message.id for message in messages]
        read_by_qs = MessageReadBy.objects.filter(message_id__in=message_ids).select_related('user__uzytkownik').order_by('id')
        read_by_map = {}
        read_by_current_user_ids = set()
        for entry in read_by_qs:
            read_by_map.setdefault(entry.message_id, []).append(entry)
            if entry.user_id == self.user.id:
                read_by_current_user_ids.add(entry.message_id)
        for message_id, entries in read_by_map.items():
            read_by_map[message_id] = entries[:10]

        user_votes = {}
        for message in messages:
            reactions = _reactions(message)
            if self.user.id in reactions.get('upvotes', []):
                user_votes[message.id] = 'upvote'
            elif self.user.id in reactions.get('downvotes', []):
                user_votes[message.id] = 'downvote'

        voter_names = {}
        if include_voters:
            voter_ids = set()
            for message in messages:
                reactions = _reactions(message)
                voter_ids.update(reactions.get('upvotes', []), reactions.get('downvotes', []))
            voter_names = _voter_names_by_id(voter_ids)

        result = [build_chat_message_event(message, include_voters=include_voters, read_by=read_by_map.get(message.id, []), voter_names=voter_names) for message in messages]
        for item, message in zip(result, messages, strict=True):
            item['read_by_current_user'] = message.id in read_by_current_user_ids

        return {'messages': result, 'users': users, 'user_votes': user_votes}

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
