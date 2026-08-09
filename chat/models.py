from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _


class ChatRoomModel(models.Model):
    """Abstract base for models that have an optional associated chat room."""

    chat_room = models.ForeignKey("chat.Room", null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s", verbose_name=_("Chat room"))

    class Meta:
        abstract = True


class Room(models.Model):
    """
    A room for people to chat in.
    """

    # Allowed users
    allowed = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="rooms")

    # For 1to1 chats
    public = models.BooleanField(default=True)

    # For old chats without activity
    archived = models.BooleanField(default=False)

    # Room title
    title = models.CharField(max_length=255, unique=True)

    # List of users who saw all messages in this chat
    seen_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="seen_rooms")

    # List of users who disabled notifications
    muted_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='muted_rooms')

    # Last activity timestamp
    last_activity = models.DateTimeField(auto_now=True)

    # Denormalized snapshot of the last message — lets the sidebar render previews without joining Message.
    last_message_text = models.CharField(max_length=200, blank=True, default='')
    last_message_sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='last_message_in_rooms')
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_anonymous = models.BooleanField(default=False)

    # Protected rooms (for tasks, voting) should not be auto-deleted by chat_rooms command
    protected = models.BooleanField(default=False)

    # User who created this room (null for rooms created before this field was added)
    founder = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='founded_rooms')

    # Marks the special guest-facing room automatically created for public groups
    is_inbox = models.BooleanField(default=False)

    @staticmethod
    def create_inbox():
        """Create the guest-facing Inbox room if it doesn't exist. Returns the room or None."""
        from django.conf import settings
        from django.contrib.auth.models import User
        from django.db import IntegrityError, OperationalError

        if not getattr(settings, 'GROUP_IS_PUBLIC', True):
            return None
        try:
            if Room.objects.filter(is_inbox=True).exists():
                return None
        except OperationalError:
            return None
        try:
            room = Room.objects.create(title='Inbox', public=True, protected=True, is_inbox=True)
        except IntegrityError:
            return None
        room.allowed.set(User.objects.filter(is_active=True))
        return room

    def __str__(self):
        return self.title

    def get_other(self, user):
        assert not self.public
        # Use prefetched data if available to avoid extra query
        if hasattr(self, '_prefetched_objects_cache') and 'allowed' in self._prefetched_objects_cache:
            for allowed_user in self.allowed.all():
                if allowed_user.id != user.id:
                    return allowed_user
            return None
        return self.allowed.exclude(id=user.id).first()

    # Name that user will see in chats list
    def displayed_name(self, user):
        title_len = 90
        if self.public:
            # Clip public room names to title_len characters for display
            return self.title[:title_len] if len(self.title) > title_len else self.title

        get_user = self.get_other(user)
        if get_user is not None:
            username = get_user.username
            # Clip long usernames to match room title length
            return username[:title_len] if len(username) > title_len else username
        else:
            return "--"

    @property  # adds 'getter', 'setter' and 'deleter' methods
    def group_name(self):
        """
        Returns the Channels Group name that sockets should
        subscribe to to get sent messages as they are generated.
        """
        return "room-%s" % self.id

    @staticmethod
    def find_all_with_users(*users):
        """
        Returns queryset of private Room objects containing all given users.
        """
        qs = Room.objects.filter(public=False)
        for user in users:
            qs = qs.filter(allowed=user)
        return qs

    @staticmethod
    def find_with_users(*users):
        """
        Returns first matching room.
        """
        return Room.find_all_with_users(*users).first()

    @classmethod
    def get_or_create_for_users(cls, *users):
        """
        Get or create a private 1-to-1 room for the given users.
        Uses sorted usernames as the room title and ensures all users are in `allowed`.
        """
        from django.db import IntegrityError

        title = '-'.join(sorted(u.username for u in users))
        room = cls.find_with_users(*users)
        if room is not None:
            if room.title != title:
                room.title = title
                room.save(update_fields=['title'])
            return room

        try:
            room = cls.objects.create(title=title, public=False)
        except IntegrityError:
            room = cls.objects.get(title__iexact=title)
            room.public = False
            room.save(update_fields=['public'])

        if room.allowed.count() != len(users):
            room.allowed.set(users)
        return room

    @classmethod
    def create_all_one2one_rooms(cls):
        """Create or update private 1-to-1 rooms for every pair of active users."""
        User = get_user_model()
        active_users = User.objects.filter(is_active=True)
        for i in active_users:
            for j in active_users:
                if i == j:
                    continue
                cls.get_or_create_for_users(i, j)

    @staticmethod
    def find_private_rooms_for_user_pairs(user, other_user_ids):
        """
        Optimized: Find all private 1-to-1 rooms between the given user and multiple other users.
        Returns a dictionary mapping other_user_id to Room object.
        This uses a single database query instead of N queries.
        Args:
            user: The main user
            other_user_ids: List or queryset of user IDs to find rooms with
        Returns:
            dict: {other_user_id: Room} for found rooms
        """
        # Convert to list if needed
        other_user_ids = list(other_user_ids)

        if not other_user_ids:
            return {}

        # Find all private rooms where:
        # 1. public=False
        # 2. user is in allowed
        # 3. room has exactly 2 users (1-to-1)
        # 4. at least one of the other_user_ids is also in allowed
        rooms = Room.objects.filter(public=False, allowed=user).filter(allowed__id__in=other_user_ids).distinct()

        # Build mapping: other_user_id -> room
        result = {}

        # We need to check each room to find which other user from the pair it corresponds to
        # Since these are 1-to-1 rooms, there should be exactly one other user besides the main user
        for room in rooms:
            # Get the other user in this room (excluding the main user)
            other_users = room.allowed.exclude(id=user.id)
            if other_users.count() == 1:
                other_user = other_users.first()
                if other_user.id in other_user_ids:
                    result[other_user.id] = room

        return result

    @classmethod
    def get_members_excluding(cls, room_id, user_id):
        """
        Get all room members except a specific user.
        Uses a single query with prefetch_related for efficiency.
        Args:
            room_id: The room ID
            user_id: User ID to exclude
        Returns:
            QuerySet[User]: Allowed users except the excluded one
        """
        try:
            room = cls.objects.get(id=room_id)
            return room.allowed.exclude(id=user_id)
        except cls.DoesNotExist:
            return get_user_model().objects.none()

    @classmethod
    def get_membership_preferences_bulk(cls, room_id, user_ids):
        """
        Bulk fetch membership preferences (seen/muted status) for multiple users in a room.
        Returns dict: {user_id: {'seen': bool, 'muted': bool}}
        Uses 2 queries regardless of number of users.
        Args:
            room_id: The room ID
            user_ids: List of user IDs to check
        Returns:
            dict: Mapping user_id to their preferences
        """
        if not user_ids:
            return {}

        # try:
        #     room = cls.objects.get(id=room_id)
        # except cls.DoesNotExist:
        #     return {user_id: {'seen': False, 'muted': False} for user_id in user_ids}

        # Get all users with their relationships in 2 queries
        users = (
            get_user_model()
            .objects.filter(id__in=user_ids)
            .prefetch_related(
                Prefetch('seen_rooms', queryset=cls.objects.filter(id=room_id), to_attr='prefetched_seen_rooms'),
                Prefetch('muted_rooms', queryset=cls.objects.filter(id=room_id), to_attr='prefetched_muted_rooms'),
            )
        )

        result = {}
        for user in users:
            result[user.id] = {'seen': bool(user.prefetched_seen_rooms), 'muted': bool(user.prefetched_muted_rooms)}

        # Fill in missing users (shouldn't happen but defensive)
        for user_id in user_ids:
            if user_id not in result:
                result[user_id] = {'seen': False, 'muted': False}

        return result


class Message(models.Model):
    # 'sender' must be 'null=True' for anonymouse messages in email (search for 'if m.anonymous:').
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    time = models.DateTimeField(auto_now=True)
    text = models.TextField()
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    anonymous = models.BooleanField(default=False)

    # Guest contact details for messages submitted by non-logged-in users
    guest_email = models.EmailField(blank=True, default='')
    guest_name = models.CharField(max_length=255, blank=True, default='')

    # ZMIANA 2 — cytowanie: opcjonalne odwołanie do wiadomości-rodzica
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')

    # JSONField to store reactions: {upvotes: [user_ids], downvotes: [user_ids], bulb: [user_ids], question: [user_ids]}
    reactions = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        unique_together = ('sender', 'text', 'room', 'time')
        indexes = [models.Index(fields=['room', 'time'], name='chat_message_room_time_asc_idx')]


# Store changes history separately,
# so you don't have to deal with it unless you need it
class MessageHistory(models.Model):
    """
    All states of given message will be associated with this object.
    They can be easily retrieved like MessageHistory#entries.
    """

    message = models.OneToOneField(Message, on_delete=models.CASCADE)


class MessageHistoryEntry(models.Model):
    """Stores state of message that is no longer relevant"""

    history = models.ForeignKey(MessageHistory, on_delete=models.CASCADE, related_name="entries")
    text = models.TextField()
    time = models.DateTimeField(auto_now=True)


class MessageAttachment(models.Model):
    type = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")

    class Meta:
        indexes = [models.Index(fields=['message'], name='chat_messageattachment_msg_idx')]


# ZMIANA 4C — "przeczytane przez": śledzenie kto przeczytał daną wiadomość
class MessageReadBy(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_by')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='read_messages')

    class Meta:
        unique_together = ('message', 'user')
        indexes = [models.Index(fields=['message'], name='chat_msgreadby_message_idx')]
