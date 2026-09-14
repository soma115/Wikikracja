"""Room membership, access and room-level read state repository."""

from channels.db import database_sync_to_async

from .models import Room


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
        from .exceptions import ClientError

        try:
            room = Room.objects.get(pk=room_id)
        except Room.DoesNotExist:
            raise ClientError('ROOM_INVALID') from None
        self.ensure_room_access(room)
        return room

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
        self.get_accessible_room_sync(room_id).muted_by.remove(self.user)

    @database_sync_to_async
    def mute_room(self, room_id):
        room = self.get_accessible_room_sync(room_id)
        if not room.muted_by.filter(id=self.user.id).exists():
            room.muted_by.add(self.user)

    @database_sync_to_async
    def get_rooms_with_notifications_enabled(self):
        return list(Room.objects.filter(allowed=self.user).exclude(muted_by=self.user))

    @database_sync_to_async
    def can_post_in_room(self, room):
        from .services import can_user_post_in_room

        return can_user_post_in_room(room, self.user)

    @database_sync_to_async
    def room_is_seen(self, room):
        from .services import is_room_seen_for_user

        return is_room_seen_for_user(self.user, room)

    @database_sync_to_async
    def see_room(self, room):
        from .services import mark_room_read_for_user

        mark_room_read_for_user(self.user, room)

    @database_sync_to_async
    def unsee_room(self, room):
        from .services import mark_room_unread_for_user

        mark_room_unread_for_user(self.user, room)

    @database_sync_to_async
    def get_unread_count(self) -> int:
        from .services import get_unread_count_for_user

        return get_unread_count_for_user(self.user)
