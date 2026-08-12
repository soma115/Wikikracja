import asyncio
import datetime
import inspect
import logging
from typing import Union

from .models import Message, Room

log = logging.getLogger(__name__)


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
            for user_id, cons in self._reg.items():
                if cons == consumer:
                    del self._reg[user_id]
                    return
        try:
            del self._reg[user.id]
        except (KeyError):
            pass  # User already removed from registry, this is normal
        except Exception as e:
            log.error(f"utils.py: Exception {str(e)} for user {user.id}")

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
        self._reg[int(room_id)] = {'joined_at': datetime.datetime.now()}

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
                return

            if receiver is not None:
                await receiver.send_json(message)
                return

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


def send_message_to_room(room_title, message_text, sender=None, anonymous=True, guest_email='', guest_name=''):
    """
    Send a message to a specific chat room
    Args:
        room_title (str): The title of the room to send the message to
        message_text (str): The message text to send
        sender (User, optional): The user sending the message. Defaults to None (system message)
        anonymous (bool, optional): Whether the message should be anonymous. Defaults to True.
        guest_email (str, optional): Email provided by a non-logged-in guest.
        guest_name (str, optional): Name and surname provided by a non-logged-in guest.
    Returns:
        Message: The created message object or None if room not found
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        from .consumers import ChatConsumer
        from .group_messages import format_chat_message

        # Create the message in the database
        try:
            room = Room.objects.get(title=room_title)
        except (Room.DoesNotExist):
            log.error(f"Room '{room_title}' does not exist")
            return None
        message = Message.objects.create(sender=sender, text=message_text, room=room, anonymous=anonymous, guest_email=guest_email, guest_name=guest_name)
        log.info(f"Message sent to room '{room_title}': {message_text[:50]}...")

        # Mark the room as unseen for all users except the sender
        users_to_mark_unseen = room.allowed.all()
        if sender:
            users_to_mark_unseen = users_to_mark_unseen.exclude(id=sender.id)

        room.seen_by.remove(*users_to_mark_unseen)

        # Send WebSocket notification to all connected clients in the room
        channel_layer = get_channel_layer()

        # Format the message data
        message_data = format_chat_message(
            room_id=room.id,
            user_id=sender.id if sender else None,
            anonymous=anonymous,
            message=message_text,
            message_id=message.id,
            new=True,
            upvotes=0,
            downvotes=0,
            edited=False,
            date=message.time,
            latest_date=message.time,
            attachments={},
        )

        # Send the message to the room group
        try:
            async_to_sync(channel_layer.group_send)(f"room-{room.id}", {"type": "chat.message", **message_data})
        except Exception as e:
            log.warning(f"Could not push chat.message to channel layer for room {room.id}: {e}")

        # Send browser notification to each online user who should receive it
        # Batch fetch muted user IDs to avoid N+1 queries
        muted_user_ids = set(room.muted_by.filter(id__in=[u.id for u in users_to_mark_unseen]).values_list('id', flat=True))

        for user in users_to_mark_unseen:
            # Skip if the user has muted the room
            if user.id in muted_user_ids:
                continue

            # Check if user is online and has an active connection
            if user.id in ChatConsumer.online_registry._reg:
                consumer = ChatConsumer.online_registry.get_consumer(user)

                try:
                    # Send notification in the same format as regular chat notifications
                    async_to_sync(consumer.send_json)(
                        {"notification": {'title': "System" if sender is None else ("Anonymous" if anonymous else sender.username), 'body': message_text[:100], 'link': None, 'room_id': room.id}}
                    )

                    # Also trigger the onRoomUnsee function to highlight the chat link
                    async_to_sync(consumer.send_json)({"unsee_room": room.id})
                except Exception as e:
                    log.warning(f"Could not push WebSocket notification to user {user.id}: {e}")

        return message
    except (Room.DoesNotExist):
        log.error(f"Room '{room_title}' not found")
        return None
    except (asyncio.CancelledError):
        log.warning(f"send_message_to_room cancelled for room '{room_title}' (async context interrupted)")
        return None
    except Exception as e:
        log.error(f"Error sending message to room '{room_title}': {str(e)}")
        return None
