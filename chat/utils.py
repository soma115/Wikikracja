import inspect
import logging
import re
from pathlib import Path
from typing import Union

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)


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
        user = consumer.scope['user']
        if not user.is_authenticated:
            for user_id, cons in list(self._reg.items()):
                if cons == consumer:
                    del self._reg[user_id]
                    return
            return
        try:
            if self._reg.get(user.id) is consumer:
                del self._reg[user.id]
        except KeyError:
            pass  # User already removed from registry, this is normal

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


class HandledMessage:
    def __init__(self):
        self.messages = []
        self._explicit_consumer = None

    def set_explicit_consumer_mode(self, consumer):
        self._explicit_consumer = consumer

    def set_implicit_consumer_mode(self):
        self._explicit_consumer = None

    def send_json(self, message: Union[dict, str, int, float], to_consumer=None, ignore_trace=False):
        self._add_message(None, message, to_consumer or self._explicit_consumer, ignore_trace)

    def group_send(self, group: str, message: dict, ignore_trace=False):
        self._add_message(group, message, None, ignore_trace)

    def _add_message(self, group, message, to_consumer, ignore_trace):
        # if handler associated with proxy already has something to respond to client,
        # do not respond with other data as well as it will cause it to be discarded
        # as that trace id will be already resolved.
        should_ignore_trace = bool([x for x in self.messages if not x[3]])
        self.messages.append([group, message, to_consumer, ignore_trace or should_ignore_trace])

    def get_messages(self):
        return self.messages

    # TODO: perhaps passing lambda to handle message and perform post-processing is a good idea
    async def send_all(self, consumer):
        """
        Sends all prepared messages in case post-processing is not needed.
        """
        for group, message, receiver, _ in self.messages:
            if group is not None:
                await consumer.channel_layer.group_send(group, message)
            elif receiver is not None:
                await receiver.send_json(message)
            else:
                await consumer.send_json(message)


class Handlers:
    def __init__(self):
        self.map = {}

    def register(self, command):
        def inner(func):
            x = inspect.getfullargspec(func)
            positional = x.args
            args = x.varargs
            kwargs = x.varkw
            defaults = x.defaults or ()
            assert positional[1] == "proxy"
            assert args is None
            assert kwargs is None

            # Calculate which parameters are required (no default value)
            all_params = positional[2:]  # Skip 'self' and 'proxy'
            num_defaults = len(defaults)
            num_required = len(all_params) - num_defaults
            required_params = all_params[:num_required]
            optional_params = all_params[num_required:]

            self.map[command] = {'handler': func, 'args': all_params, 'required': required_params, 'optional': optional_params}
            return func

        return inner


def helper_method(helper):
    """
    Helper methods are called from handlers.
    Problem is every time we add WS message tp proxy-object
    we don't specify consumer, assuming all messages we send are sent
    to consumer who sent message to trigger this handler.
    However it is possible that specific consumer triggered handler
    that needs to send message to another consumer. If this message is sent from helper method
    like this 'consumer.some_helper_method(proxy, arg1, arg2, ...)' then proxy will store
    those requests as if they were for user who triggered handler.
    This is why consumer has to be specified explicitly.
    This decoratror will change proxy mode to 'explicit consumer',
    call handler with this proxy and then change mode back to normal.
    This way we can avoid the need to specify to_consumer=self every time
    that would make overall code shorter by half length of this comment.
    """

    async def inner(consumer, proxy, *args, **kwargs):
        proxy.set_explicit_consumer_mode(consumer)
        return_value = await helper(consumer, proxy, *args, **kwargs)
        proxy.set_implicit_consumer_mode()
        return return_value

    return inner
