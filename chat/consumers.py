import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from core.notifications import NOTIF_LOG_TAG
from core.presence import PRESENCE_GROUP, get_presence_status, record_presence

from .command_handlers import ChatCommandHandlers
from .exceptions import ClientError
from .room_repository import ChatRoomRepository
from .serializers import build_chat_message_payload
from .services import ChatRepository, get_avatar_url
from .utils import OnlineUserRegistry, RoomRegistry

log = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    This chat consumer handles websocket connections for chat clients.
    """

    online_registry = OnlineUserRegistry()

    @property
    def repo(self):
        return ChatRepository(self.scope['user'])

    @property
    def room_repo(self):
        return ChatRoomRepository(self.scope['user'])

    # WebSocket event handlers
    async def connect(self):
        """
        Called when the websocket is handshaking as part of initial connection.
        """
        # Are they logged in?
        if self.scope["user"].is_anonymous:
            # Reject the connection
            log.warning(f"WebSocket connection rejected: user is anonymous. Session data: {self.scope.get('session', {})}")
            await self.close()
        else:
            # Accept the connection
            log.info(f"WebSocket connection accepted for user: {self.scope['user'].username}")
            await self.accept()

            # register user as online
            ChatConsumer.online_registry.make_online(self.scope['user'], self)

            # join personal group for user-targeted pushes (e.g. unread count)
            await self.channel_layer.group_add(f"user_{self.scope['user'].id}", self.channel_name)

            # send current unread count and own presence immediately on connect
            count = await self.room_repo.get_unread_count()
            presence_update = await self.record_presence('app')
            initial_response = {"unread_count": count}
            if presence_update:
                initial_response['presence_update'] = presence_update
            await self.send_json(initial_response)

            if presence_update:
                await self.channel_layer.group_send(PRESENCE_GROUP, {'type': 'presence.update', **presence_update})
            await self.channel_layer.group_add(PRESENCE_GROUP, self.channel_name)

            await ChatCommandHandlers(self, ChatConsumer.online_registry).send_online_update(True)

        # Store which rooms the user has joined on this connection
        self.rooms = RoomRegistry()

    async def disconnect(self, code):
        """
        Called when the WebSocket closes for any reason.
        """
        if self.scope['user'].is_anonymous:
            return

        # Leave all the rooms we are still in
        command_handlers = ChatCommandHandlers(self, ChatConsumer.online_registry)
        for room_id in self.rooms.items():
            try:
                await command_handlers.leave(room_id)
            except ClientError:
                pass

        await self.channel_layer.group_discard(PRESENCE_GROUP, self.channel_name)
        # leave personal group
        await self.channel_layer.group_discard(f"user_{self.scope['user'].id}", self.channel_name)

        # remove user from online list
        ChatConsumer.online_registry.make_offline(self)

        await command_handlers.send_online_update(False)

    async def receive_json(self, content):
        """
        Called when we get a text frame. Channels will JSON-decode
        the payload for us and pass it as the first argument.
        """
        # Messages will have a "command" key we can switch on
        command = content.get("command", None)

        # trace id is a identifier attached to the message by client,
        # that makes request and hopes to get response back with same trace id.
        trace_id = content.get("__TRACE_ID")

        if not ChatCommandHandlers.handles(command):
            return
        try:
            result = await ChatCommandHandlers(self, ChatConsumer.online_registry).dispatch(command, content)
            for index, response in enumerate(result.responses):
                if index == 0:
                    response['__TRACE_ID'] = trace_id
                await self.send_json(response)
        except ClientError as e:
            error = {'error': e.code}
            if e.code != 'DATA_MISSING':
                error['__TRACE_ID'] = trace_id
            await self.send_json(error)

    @database_sync_to_async
    def record_presence(self, source):
        changed = record_presence(self.scope['user'], source)
        if changed:
            profile = self.scope['user'].uzytkownik
            return {
                'user_id': self.scope['user'].id,
                'status': get_presence_status(profile.last_presence_at),
                'source': profile.last_presence_source,
                'timestamp': profile.last_presence_at.isoformat() if profile.last_presence_at else None,
            }
        return None

    async def push_unread_count(self):
        """Push updated unread room count to all connections of this user."""
        count = await self.room_repo.get_unread_count()
        await self.channel_layer.group_send(f"user_{self.scope['user'].id}", {"type": "chat.unread_count", "count": count})

    async def chat_unread_count(self, event):
        """Channel layer handler — relays unread count to the WebSocket client."""
        await self.send_json({"unread_count": event["count"]})

    async def chat_room_unread(self, event):
        """Relay a per-room unread counter update to every user's tab."""
        if event["room_id"] in self.rooms.items():
            return
        payload = {"room_id": event["room_id"]}
        if "count" in event:
            payload["count"] = event["count"]
        else:
            payload["delta"] = event.get("delta", 0)
        await self.send_json({"room_unread_count": payload})

    async def chat_notification(self, event):
        """Channel layer handler — relay a new-message notification to the client.

        Skip if the user is already in the room. The client shows an actual OS
        notification via the service worker (see utility.js::makeNotification),
        so it appears immediately even while the tab is in the foreground.
        Push (FCM) is a fallback for when the tab/browser is fully closed.
        """
        notification_id = event["notification"].get("notification_id", "?")
        if event["room_id"] in self.rooms.items():
            log.debug(f"{NOTIF_LOG_TAG} chat_notification notification_id={notification_id} skipped for user {self.scope['user'].id}: already present in room {event['room_id']}")
            return
        log.debug(f"{NOTIF_LOG_TAG} chat_notification notification_id={notification_id} relayed to user {self.scope['user'].id} over WebSocket")
        await self.send_json({"notification": event["notification"]})

    async def chat_mention(self, event):
        """Channel layer handler — relay a mention notification to the client.

        Skip if the user is already in the room where the mention happened.
        Same dual delivery as chat_notification: WS for foreground, push for
        when the tab/browser is closed.
        """
        notification_id = event["notification"].get("notification_id", "?")
        if event["room_id"] in self.rooms.items():
            log.debug(f"{NOTIF_LOG_TAG} chat_mention notification_id={notification_id} skipped for user {self.scope['user'].id}: already present in room {event['room_id']}")
            return
        log.debug(f"{NOTIF_LOG_TAG} chat_mention notification_id={notification_id} relayed to user {self.scope['user'].id} over WebSocket")
        await self.send_json({"notification": event["notification"]})

    async def event_notification(self, event):
        """Channel layer handler — relay an event notification to the client."""
        await self.send_json({"notification": event["notification"]})

    async def vote_notification(self, event):
        """Channel layer handler — relay a voting notification to the client."""
        await self.send_json({"notification": event["notification"]})

    async def citizen_notification(self, event):
        """Channel layer handler — relay a citizenship/people notification to the client."""
        await self.send_json({"notification": event["notification"]})

    async def post_notification(self, event):
        """Channel layer handler — relay a board document notification to the client."""
        await self.send_json({"notification": event["notification"]})

    async def task_notification(self, event):
        """Channel layer handler — relay a task/activity notification to the client."""
        await self.send_json({"notification": event["notification"]})

    async def survey_notification(self, event):
        """Channel layer handler — relay a survey notification to the client."""
        await self.send_json({"notification": event["notification"]})

    ###########################################################
    # Handlers for messages sent over the channel layer       #
    ###########################################################

    async def presence_update(self, event):
        await self.send_json({'presence_update': {'user_id': event['user_id'], 'status': event['status'], 'source': event['source'], 'timestamp': event['timestamp']}})

    async def chat_message(self, event):
        user = await self.repo.get_user_by_id(event["user_id"])
        vote = await self.repo.get_vote(event['message_id'])
        vote_value = vote.vote if vote is not None else None
        avatar_url = get_avatar_url(user)
        message = build_chat_message_payload(event, user=user, vote_value=vote_value, current_user=self.scope['user'], avatar_url=avatar_url)
        await self.send_json({"messages": [message]})

    async def chat_vote(self, event):
        update = {**event['update_votes']}
        who_triggered = update['user_id']
        update["your_vote"] = update['vote'] if who_triggered == self.scope["user"].id else None
        del update['vote']
        await self.send_json({"update_votes": update})

    async def chat_edit(self, event):
        edit = event['edit_message']
        await self.send_json({"edit_message": edit})

    async def chat_reaction(self, event):
        update = {**event['update_reactions']}
        who_triggered = update['user_id']
        update['your_reaction'] = update['reaction'] if who_triggered == self.scope['user'].id else None
        await self.send_json({"update_reactions": update})

    async def chat_read(self, event):
        await self.send_json({"messages_read": event['messages_read']})
