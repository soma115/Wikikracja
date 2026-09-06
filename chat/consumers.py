import logging
import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from zzz.notifications import NOTIF_LOG_TAG
from zzz.richtext import sanitize

from .exceptions import ClientError
from .serializers import build_chat_message_payload
from .services import ChatRepository, get_avatar_url, send_message
from .utils import HandledMessage, Handlers, OnlineUserRegistry, RoomRegistry, get_upload_path, helper_method

log = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    This chat consumer handles websocket connections for chat clients.
    """

    handlers = Handlers()
    online_registry = OnlineUserRegistry()

    @property
    def repo(self):
        return ChatRepository(self.scope['user'])

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

            # send current unread count immediately on connect
            count = await self.repo.get_unread_count()
            await self.send_json({"unread_count": count})

            proxy = HandledMessage()
            await self.send_online_update(proxy, True)
            await proxy.send_all(self)

        # Store which rooms the user has joined on this connection
        self.rooms = RoomRegistry()

    async def disconnect(self, code):
        """
        Called when the WebSocket closes for any reason.
        """
        if self.scope['user'].is_anonymous:
            return

        # Leave all the rooms we are still in
        for room_id in self.rooms.items():
            try:
                proxy = HandledMessage()
                await self.leave_room(proxy, room_id)
                await proxy.send_all(self)
            except ClientError:
                pass

        # leave personal group
        await self.channel_layer.group_discard(f"user_{self.scope['user'].id}", self.channel_name)

        # remove user from online list
        ChatConsumer.online_registry.make_offline(self)

        proxy = HandledMessage()
        await self.send_online_update(proxy, False)
        await proxy.send_all(self)

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

        handler_data = ChatConsumer.handlers.map.get(command)
        # Unknown command
        if handler_data is None:
            return

        handler = handler_data.get('handler')
        arg_names = handler_data.get('args')
        required_args = handler_data.get('required', [])
        args = {}

        # Check required parameters
        for arg_name in required_args:
            arg = content.get(arg_name)
            if arg is None:
                return await self.send_json({"error": "DATA_MISSING"})
            args[arg_name] = arg

        # Add optional parameters if provided
        for arg_name in arg_names:
            if arg_name not in args:
                arg = content.get(arg_name)
                if arg is not None:
                    args[arg_name] = arg

        try:
            result = HandledMessage()
            await handler(self=self, proxy=result, **args)
            for group, message, to_consumer, ignore_trace in result.get_messages():
                if group is None:
                    if to_consumer:
                        await to_consumer.send_json(message)
                    else:
                        if not ignore_trace:
                            message['__TRACE_ID'] = trace_id
                        await self.send_json(message)
                else:
                    await self.channel_layer.group_send(group, message)
        except ClientError as e:
            await self.send_json({"error": e.code, "__TRACE_ID": trace_id})

    #################################################
    # Command helper methods called by receive_json #
    #################################################

    @handlers.register("join")
    async def join_room(self, proxy: HandledMessage, room_id: int):
        room = await self.repo.get_room_or_error(room_id)

        # user can only be in one room at the time
        for room_id_to_leave in self.rooms.items():
            try:
                room_to_leave = await self.repo.get_room_or_error(room_id_to_leave)
            except ClientError:
                self.rooms.leave(room_id_to_leave)
                continue
            await self.handle_leave_room(room_to_leave)

        self.rooms.join(room_id)

        await self.channel_layer.group_add(room.group_name, self.channel_name)

        proxy.send_json({"join": str(room.id), "title": room.title, "public": room.public, "notifications": not await self.repo.has_muted_room(room.id), "can_post": await self.repo.can_post_in_room(room)})

        batch_data = await self.repo.get_recent_messages_batch(room_id, self.scope['user'].id, limit=100, include_voters=room.source_app == 'tasks')
        messages_list = batch_data['messages']
        users_dict = batch_data['users']
        user_votes_dict = batch_data['user_votes']

        to_send = []
        current_user = self.scope['user']
        for event in messages_list:
            user = users_dict.get(event['user_id'])
            vote_value = user_votes_dict.get(event['message_id'])
            avatar_url = get_avatar_url(user)
            to_send.append(build_chat_message_payload(event, user=user, vote_value=vote_value, current_user=current_user, avatar_url=avatar_url))

        if to_send:
            proxy.send_json({'messages': to_send})

    @handlers.register("leave")
    async def leave_room(self, proxy: HandledMessage, room_id):
        room = await self.repo.get_room_or_error(room_id)
        await self.handle_leave_room(room)
        proxy.send_json({"leave": str(room.id)})

    @handlers.register("fetch-messages")
    async def fetch_messages(self, proxy: HandledMessage, room_id, sort_by='date', order='desc', popular_only=False):
        room = await self.repo.get_room_or_error(room_id)

        if sort_by not in ('date', 'likes'):
            sort_by = 'date'
        if order not in ('asc', 'desc'):
            order = 'desc'
        popular_only = bool(popular_only)

        batch_data = await self.repo.get_recent_messages_batch(room_id, self.scope['user'].id, limit=100, sort_by=sort_by, order=order, popular_only=popular_only, include_voters=room.source_app == 'tasks')
        messages_list = batch_data['messages']
        users_dict = batch_data['users']
        user_votes_dict = batch_data['user_votes']

        to_send = []
        current_user = self.scope['user']
        for event in messages_list:
            user = users_dict.get(event['user_id'])
            vote_value = user_votes_dict.get(event['message_id'])
            avatar_url = get_avatar_url(user)
            to_send.append(build_chat_message_payload(event, user=user, vote_value=vote_value, current_user=current_user, avatar_url=avatar_url))

        proxy.send_json({'replace_messages': True, 'room_id': str(room_id), 'messages': to_send})

    @handlers.register("send")
    async def send_message_to_room(self, proxy: HandledMessage, room_id, message, is_anonymous, attachments, reply_to_id=None, temp_id=None):
        try:
            room_id = int(room_id)
        except (TypeError, ValueError):
            raise ClientError("ROOM_INVALID") from None
        if room_id not in self.rooms.items():
            raise ClientError("ROOM_ACCESS_DENIED")

        if attachments is None:
            attachments = {}
        if not isinstance(attachments, dict):
            raise ClientError("BAD_ATTACHMENT_TYPE")
        for key, value in attachments.items():
            if key not in ('images',):
                raise ClientError("BAD_ATTACHMENT_TYPE")
            if not isinstance(value, (list, tuple)):
                raise ClientError("BAD_ATTACHMENT_TYPE")
            for filename in value:
                if not isinstance(filename, str):
                    raise ClientError("BAD_ATTACHMENT_TYPE")

        room = await self.repo.get_room_or_error(room_id)
        await send_message(
            room,
            message,
            sender=self.scope["user"],
            anonymous=is_anonymous,
            attachments=attachments,
            reply_to_id=reply_to_id,
            temp_id=temp_id,
            linkify=False,
            channel_layer=self.channel_layer,
            online_registry=ChatConsumer.online_registry,
            background=True,
        )

    async def _dispatch_proxy(self, proxy: HandledMessage):
        """Flush a proxy outside of receive_json — used by background tasks that build messages via helpers."""
        for group, message, to_consumer, _meta in proxy.get_messages():
            try:
                if group is not None:
                    await self.channel_layer.group_send(group, message)
                elif to_consumer is not None:
                    await to_consumer.send_json(message)
                else:
                    await self.send_json(message)
            except Exception as e:
                log.warning(f"Failed to dispatch proxy message: {e}")

    @handlers.register("get-online-users")
    async def send_online_users(self, proxy: HandledMessage):
        scoped_user = self.scope['user']
        online_users = ChatConsumer.online_registry.get_online()
        other_user_ids = [uid for uid in online_users if uid != scoped_user.id]
        rooms_dict = await self.repo.find_private_rooms_for_user_pairs(scoped_user, other_user_ids)
        online_data = []
        for online_user_id in other_user_ids:
            room = rooms_dict.get(online_user_id)
            if room is not None:
                online_data.append({'user_id': online_user_id, 'room_id': room.id, 'online': True})
        proxy.send_json({'online_data': online_data})

    @handlers.register("room-seen")
    async def handle_seen_room(self, proxy: HandledMessage, room_id):
        try:
            room = await self.repo.get_room_or_error(room_id)
        except ClientError:
            return
        if not await self.repo.room_is_seen(room):
            await self.repo.see_room(room)
            await self.push_unread_count()

    @handlers.register("room-unseen")
    async def handle_unseen_room(self, proxy: HandledMessage, room_id):
        try:
            room = await self.repo.get_room_or_error(room_id)
        except ClientError:
            return
        await self.repo.unsee_room(room)
        await self.push_unread_count()

    async def push_unread_count(self):
        """Push updated unread room count to all connections of this user."""
        count = await self.repo.get_unread_count()
        await self.channel_layer.group_send(f"user_{self.scope['user'].id}", {"type": "chat.unread_count", "count": count})

    async def chat_unread_count(self, event):
        """Channel layer handler — relays unread count to the WebSocket client."""
        await self.send_json({"unread_count": event["count"]})

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

    @handlers.register("message-add-vote")
    async def handle_add_vote(self, proxy: HandledMessage, vote: str, message_id: int):
        existing_vote = await self.repo.get_vote(message_id)
        opposite_vote_events = {"upvote": "downvote", "downvote": "upvote"}

        if existing_vote is not None:
            if existing_vote.vote == vote:
                return
            opposite_event = opposite_vote_events.get(vote)
            if opposite_event is not None:
                await self.repo.remove_vote(opposite_event, message_id)

        upvotes, downvotes = await self.repo.add_vote(vote, message_id)
        await self._broadcast_vote_update(proxy, message_id, vote, upvotes, downvotes, add=True)

    @handlers.register("message-remove-vote")
    async def handle_remove_vote(self, proxy: HandledMessage, vote: str, message_id: int):
        upvotes, downvotes = await self.repo.remove_vote(vote, message_id)
        await self._broadcast_vote_update(proxy, message_id, vote, upvotes, downvotes, add=False)

    async def _broadcast_vote_update(self, proxy: HandledMessage, message_id: int, vote: str, upvotes: int, downvotes: int, add: bool):
        room = await self.repo.get_room_by_message(message_id)
        update_votes = {"message_id": message_id, "upvotes": upvotes, "downvotes": downvotes, "user_id": self.scope['user'].id, "vote": vote, "add": add}
        # W pokojach zadań głosy są jawne — dołączamy nicki głosujących do tooltipów łapek.
        if room.source_app == 'tasks':
            update_votes.update(await self.repo.get_vote_voters(message_id))
        proxy.group_send(room.group_name, {"type": "chat.vote", "update_votes": update_votes})

    @handlers.register("message-react")
    async def handle_message_react(self, proxy: HandledMessage, reaction: str, message_id: int):
        valid_reactions = dict([('bulb', '💡'), ('question', '❓')])
        if reaction not in valid_reactions:
            raise ClientError("INVALID_REACTION")

        added = await self.repo.toggle_reaction(reaction, message_id)
        counts = await self.repo.get_reaction_counts(message_id)
        room = await self.repo.get_room_by_message(message_id)

        proxy.group_send(room.group_name, {"type": "chat.reaction", "update_reactions": {"message_id": message_id, "reaction": reaction, "counts": counts, "user_id": self.scope['user'].id, "added": added}})

    @handlers.register("message-mark-read")
    async def handle_mark_read(self, proxy: HandledMessage, message_id: int):
        await self.repo.mark_message_read(message_id)
        read_by = await self.repo.get_read_by_data(message_id)
        room = await self.repo.get_room_by_message(message_id)
        proxy.group_send(room.group_name, {"type": "chat.read", "messages_read": {"message_id": message_id, "read_by": read_by}})

    @handlers.register("messages-mark-read-bulk")
    async def handle_mark_read_bulk(self, proxy: HandledMessage, message_ids: list, room_id: int):
        room = await self.repo.get_room_or_error(room_id)
        new_ids = await self.repo.mark_messages_read_bulk(message_ids, room.id)
        for message_id in new_ids:
            read_by = await self.repo.get_read_by_data(message_id)
            proxy.group_send(room.group_name, {"type": "chat.read", "messages_read": {"message_id": message_id, "read_by": read_by}})

    @handlers.register("edit-message")
    async def handle_edit_message(self, proxy: HandledMessage, message_id: int, new_message: str = None, attachments: dict = None, removed_attachments: list = None):
        message = await self.repo.get_message(message_id)
        if await self.repo.get_message_sender(message) != self.scope['user']:
            raise ClientError("ACCESS_DENIED")

        if new_message is None:
            new_message = message.text
        else:
            new_message = sanitize(new_message, linkify=False)
            new_message = re.sub(r'(<br\s*/?>)+$', '', new_message).rstrip()

        if attachments is None:
            attachments = {}
        if not isinstance(attachments, dict):
            raise ClientError("BAD_ATTACHMENT_TYPE")
        for key, value in attachments.items():
            if key not in ('images',):
                raise ClientError("BAD_ATTACHMENT_TYPE")
            if not isinstance(value, (list, tuple)):
                raise ClientError("BAD_ATTACHMENT_TYPE")
            for filename in value:
                if not isinstance(filename, str):
                    raise ClientError("BAD_ATTACHMENT_TYPE")
                path = get_upload_path(filename)
                if path is None or not path.is_file():
                    raise ClientError("FILE_NOT_FOUND")

        if removed_attachments:
            if not isinstance(removed_attachments, (list, tuple)):
                raise ClientError("BAD_ATTACHMENT_TYPE")
            await self.repo.remove_attachments(message_id, removed_attachments)

        if attachments:
            await self.repo.save_attachments(message_id, attachments)

        updated_attachments = await self.repo.load_attachments(message_id)

        text_changed = message.text != new_message
        attachments_changed = bool(attachments) or bool(removed_attachments)

        if not text_changed and not attachments_changed:
            return

        room = await self.repo.get_room_by_message(message_id)

        if text_changed:
            state = await self.repo.edit_message_and_history(message_id, new_message)
            timestamp = int(state.time.timestamp()) * 1000
        else:
            timestamp = int(timezone.now().timestamp()) * 1000

        is_last = await self.repo.is_last_message_in_room(message_id, room.id)
        proxy.group_send(
            room.group_name,
            {
                "type": "chat.edit",
                "edit_message": {
                    "message_id": message_id,
                    "room_id": room.id,
                    "user_id": self.scope['user'].id,
                    "username": self.scope['user'].username,
                    "anonymous": message.anonymous,
                    "is_last_message": is_last,
                    "text": new_message,
                    "timestamp": timestamp,
                    "attachments": updated_attachments,
                },
            },
        )

    @handlers.register("get-message-history")
    async def send_message_history(self, proxy: HandledMessage, message_id):
        message_states = await self.repo.get_message_states(message_id)
        proxy.send_json({"message_history": message_states})

    @handlers.register("toggle-notifications")
    async def toggle_notifications(self, proxy, room_id, enabled):
        if enabled:
            await self.repo.unmute_room(room_id)
        else:
            await self.repo.mute_room(room_id)

    @handlers.register("get-notifications-data")
    async def get_notifications_data(self, proxy):
        rooms = await self.repo.get_rooms_with_notifications_enabled()
        proxy.send_json({'rooms': [room.id for room in rooms]})

    ##########################################################
    # Helper functions called by custom or built-in handlers #
    ##########################################################

    @helper_method
    async def send_online_update(self, proxy: HandledMessage, is_online):
        updated_user = self.scope['user']
        for room_with_user in await self.repo.find_rooms_with(updated_user):
            user_to_notify = await database_sync_to_async(lambda x, room=room_with_user: room.get_other(x))(updated_user)
            if not ChatConsumer.online_registry.is_online(user_to_notify):
                continue
            consumer = ChatConsumer.online_registry.get_consumer(user_to_notify)
            proxy.send_json({'online_data': [{'user_id': updated_user.id, 'room_id': room_with_user.id, 'online': is_online}]}, to_consumer=consumer)

    async def handle_leave_room(self, room):
        self.rooms.leave(room.id)
        await self.channel_layer.group_discard(room.group_name, self.channel_name)

    ###########################################################
    # Handlers for messages sent over the channel layer       #
    ###########################################################

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
