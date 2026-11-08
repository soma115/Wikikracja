"""Room membership, access and room-level read state repository."""

from channels.db import database_sync_to_async
from django.core.cache import cache
from django.db.models import Count

from core.presence import presence_data
from core.utils import citizen_color_class, user_display_name, user_initials

from .exceptions import ClientError
from .models import Message, MessageReadBy, Room

CHAT_UNREAD_CACHE_KEY = "chat_unread:{user_id}"
CHAT_UNREAD_CACHE_TTL = 300


class ChatRoomRepository:
    """Persisted room operations scoped to one authenticated user."""

    def __init__(self, user):
        self.user = user

    def ensure_room_access(self, room):
        if not self.user.is_authenticated:
            from .exceptions import ClientError

            raise ClientError('USER_HAS_TO_LOGIN')
        if not room.public and not room.allowed.filter(id=self.user.id).exists():
            from .exceptions import ClientError

            raise ClientError('ACCESS_DENIED')

    def get_accessible_room_sync(self, room_id):
        try:
            room = Room.objects.get(pk=room_id)
        except Room.DoesNotExist:
            raise ClientError('ROOM_INVALID') from None
        self.ensure_room_access(room)
        return room

    def get_accessible_message_sync(self, message_id, room_id=None):
        try:
            message = Message.objects.select_related('room').get(pk=message_id)
        except Message.DoesNotExist:
            raise ClientError("MESSAGE_INVALID") from None
        if room_id is not None and message.room_id != room_id:
            raise ClientError("ACCESS_DENIED")
        self.ensure_room_access(message.room)
        return message

    def _unread_messages(self, room_ids=None):
        messages = Message.objects.exclude(room__seen_by=self.user).exclude(sender_id=self.user.id).exclude(read_by__user_id=self.user.id)
        if room_ids is not None:
            messages = messages.filter(room_id__in=room_ids)
        return messages

    def _invalidate_unread_cache(self):
        cache.delete(CHAT_UNREAD_CACHE_KEY.format(user_id=self.user.id))

    def mark_room_read_sync(self, room):
        message_ids = Message.objects.filter(room=room).exclude(sender_id=self.user.id).values_list('id', flat=True)
        MessageReadBy.objects.bulk_create([MessageReadBy(message_id=message_id, user_id=self.user.id) for message_id in message_ids], ignore_conflicts=True)
        room.seen_by.add(self.user)
        self._invalidate_unread_cache()

    def mark_message_read_for_user_sync(self, message):
        MessageReadBy.objects.get_or_create(message=message, user=self.user)
        message.room.seen_by.add(self.user)
        self._invalidate_unread_cache()

    def mark_room_unread_sync(self, room, unread_message_id=None):
        if unread_message_id is not None:
            self.mark_room_unread_for_users_sync(room.id, [self.user.id], unread_message_id)
            return
        MessageReadBy.objects.filter(message__room=room, user_id=self.user.id).exclude(message__sender_id=self.user.id).delete()
        room.seen_by.remove(self.user)
        self._invalidate_unread_cache()

    def mark_message_unread_for_user_sync(self, message):
        MessageReadBy.objects.filter(message=message, user_id=self.user.id).delete()
        message.room.seen_by.remove(self.user)
        self._invalidate_unread_cache()

    @staticmethod
    def mark_room_unread_for_users_sync(room_id, user_ids, unread_message_id):
        user_ids = set(user_ids)
        if not user_ids:
            return

        seen_user_ids = set(Room.seen_by.through.objects.filter(room_id=room_id, user_id__in=user_ids).values_list('user_id', flat=True))
        if seen_user_ids:
            messages = Message.objects.filter(room_id=room_id).exclude(pk=unread_message_id).values_list('id', 'sender_id')
            MessageReadBy.objects.bulk_create(
                [MessageReadBy(message_id=message_id, user_id=user_id) for message_id, sender_id in messages for user_id in seen_user_ids if sender_id != user_id], ignore_conflicts=True
            )

        MessageReadBy.objects.filter(message_id=unread_message_id, user_id__in=user_ids).delete()
        Room.seen_by.through.objects.filter(room_id=room_id, user_id__in=user_ids).delete()
        cache.delete_many([CHAT_UNREAD_CACHE_KEY.format(user_id=user_id) for user_id in user_ids])

    def room_is_seen_sync(self, room) -> bool:
        return not self._unread_messages([room.id]).exists()

    def get_unread_count_sync(self) -> int:
        key = CHAT_UNREAD_CACHE_KEY.format(user_id=self.user.id)
        cached = cache.get(key)
        if cached is not None:
            return cached
        count = self._unread_messages().filter(room__allowed=self.user, room__archived=False).values('room_id').distinct().count()
        cache.set(key, count, CHAT_UNREAD_CACHE_TTL)
        return count

    def get_unseen_room_ids_sync(self) -> set[int]:
        return set(self._unread_messages().values_list('room_id', flat=True).distinct())

    def get_unread_message_counts_for_rooms_sync(self, room_ids) -> dict[int, int]:
        room_ids = {room_id for room_id in room_ids if room_id}
        if not room_ids or not getattr(self.user, "is_authenticated", False):
            return {}
        return dict(self._unread_messages(room_ids).values("room_id").annotate(count=Count("id")).values_list("room_id", "count"))

    @database_sync_to_async
    def get_room_or_error(self, room_id):
        return self.get_accessible_room_sync(room_id)

    @database_sync_to_async
    def find_rooms_with(self, *users):
        return list(Room.find_all_with_users(*users))

    @database_sync_to_async
    def find_private_rooms_for_user_pairs(self, user, other_user_ids):
        return Room.find_private_rooms_for_user_pairs(user, other_user_ids)

    @database_sync_to_async
    def has_muted_room(self, room_id):
        room = self.get_accessible_room_sync(room_id)
        return Room.muted_by.through.objects.filter(room_id=room.id, user_id=self.user.id).exists()

    @database_sync_to_async
    def user_has_muted_room(self, user_id, room_id):
        return Room.muted_by.through.objects.filter(room_id=room_id, user_id=user_id).exists()

    @database_sync_to_async
    def unmute_room(self, room_id):
        room = self.get_accessible_room_sync(room_id)
        room.muted_by.remove(self.user)
        room.manually_muted_by.remove(self.user)

    @database_sync_to_async
    def mute_room(self, room_id):
        room = self.get_accessible_room_sync(room_id)
        room.muted_by.add(self.user)
        room.manually_muted_by.add(self.user)

    @database_sync_to_async
    def get_rooms_with_notifications_enabled(self):
        return list(Room.objects.filter(allowed=self.user).exclude(muted_by=self.user))

    @database_sync_to_async
    def can_post_in_room(self, room):
        from .services import can_user_post_in_room

        return can_user_post_in_room(room, self.user)

    @database_sync_to_async
    def room_is_seen(self, room):
        return self.room_is_seen_sync(room)

    @database_sync_to_async
    def see_room(self, room):
        self.mark_room_read_sync(room)

    @database_sync_to_async
    def unsee_room(self, room, unread_message_id=None):
        self.mark_room_unread_sync(room, unread_message_id)

    @database_sync_to_async
    def mark_message_read(self, message_id: int):
        message = self.get_accessible_message_sync(message_id)
        MessageReadBy.objects.get_or_create(message=message, user=self.user)
        self._invalidate_unread_cache()

    @database_sync_to_async
    def mark_messages_read_bulk(self, message_ids: list, room_id: int) -> list:
        room = self.get_accessible_room_sync(room_id)
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
            MessageReadBy.objects.bulk_create([MessageReadBy(message_id=message_id, user=self.user) for message_id in new_ids], ignore_conflicts=True)
            self._invalidate_unread_cache()
        return list(new_ids)

    @database_sync_to_async
    def get_read_by_data(self, message_id: int) -> list:
        message = self.get_accessible_message_sync(message_id)
        entries = MessageReadBy.objects.filter(message=message).select_related('user__uzytkownik').order_by('id')[:10]
        from .serializers import get_avatar_url

        result = []
        for entry in entries:
            user = entry.user
            result.append(
                {
                    'user_id': user.id,
                    'username': user.username,
                    'display_name': user_display_name(user),
                    'initials': user_initials(user),
                    'avatar_url': get_avatar_url(user) or "/static/home/images/favicon.ico",
                    'citizen_color_class': citizen_color_class(user.username),
                    **presence_data(user),
                }
            )
        return result

    @database_sync_to_async
    def get_unread_count(self) -> int:
        return self.get_unread_count_sync()
