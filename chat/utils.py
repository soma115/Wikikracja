import re
from pathlib import Path

from django.conf import settings
from django.utils import timezone


def get_upload_path(filename):
    """Return a safe absolute Path for an uploaded attachment, or None if the filename is unsafe.

    Guards against path traversal (e.g. ``../../etc/passwd``) by rejecting
    directory components, rejecting parent references and checking that the
    resolved path stays inside ``MEDIA_ROOT/uploads``.
    """
    if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', filename) or '..' in filename:
        return None
    upload_dir = Path(settings.MEDIA_ROOT) / 'uploads'
    try:
        upload_dir_resolved = upload_dir.resolve()
        target = (upload_dir / filename).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if not target.is_relative_to(upload_dir_resolved):
        return None
    return target


# added those wrappers to encapsulate underlying data structure
# in case we want to change a way data is stored
class OnlineUserRegistry:
    """Utility class to keep track of users who are currently connected to websocket"""

    def __init__(self):
        self._reg = {}

    def make_online(self, user, consumer):
        self._reg[user.id] = consumer

    def make_offline(self, consumer):
        """Remove a connection and return whether the user is now offline."""
        user = consumer.scope['user']
        if not user.is_authenticated:
            for user_id, registered_consumer in list(self._reg.items()):
                if registered_consumer is consumer:
                    del self._reg[user_id]
                    return True
            return False

        if self._reg.get(user.id) is not consumer:
            return False
        del self._reg[user.id]
        return True

    def is_online(self, user):
        if user is not None:
            return self._reg.get(user.id)

    def get_online(self):
        return list(self._reg.keys())

    def get_consumer(self, user):
        return self._reg.get(user.id)


class RoomRegistry:
    def __init__(self):
        self._reg = {}

    def join(self, room_id):
        self._reg[int(room_id)] = {'joined_at': timezone.now()}

    def leave(self, room_id):
        if self._reg.get(int(room_id)):
            del self._reg[int(room_id)]

    def present(self, room):
        return self._reg.get(room.id) is not None

    def items(self):
        return list(self._reg.keys())

    def clear(self):
        self._reg.clear()
