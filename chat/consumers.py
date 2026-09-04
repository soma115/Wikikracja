import asyncio
import logging
import os
import re
import uuid
from datetime import datetime

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _

from zzz.notifications import NOTIF_LOG_TAG
from zzz.richtext import sanitize
from zzz.utils import get_site_domain

from .exceptions import ClientError
from .group_messages import format_chat_message
from .models import Message, Room
from .serializers import build_chat_message_payload
from .services import CHAT_UNREAD_CACHE_KEY, ChatRepository, extract_mentions, get_avatar_url
from .utils import HandledMessage, Handlers, OnlineUserRegistry, RoomRegistry, helper_method

log = logging.getLogger(__name__)
domain = get_site_domain()


def _build_chat_notification(author, room_id, room_name=None):
    """Build the title/body/icon/click_action shared by WS and FCM chat notifications.

    `room_name` should be the public room title, or the other participant's
    username for private chats. Pass None/"" to fall back to a generic "Chat" title.
    """
    site_url = f"https://{domain}"
    notification_id = uuid.uuid4().hex
    log.debug(f"{NOTIF_LOG_TAG} Built chat notification {notification_id} for room {room_id} (author={author})")
    return {
        'notification_id': notification_id,
        'title': _("Room: %(room)s") % {'room': room_name} if room_name else _("Chat"),
        'body': _("Sender: %(author)s") % {'author': author},
        'icon': f"{site_url}/favicon.ico",
        'click_action': f"{site_url}/chat#room_id={room_id}",
    }


def _room_notification_name(room, sender):
    """Room name to display in notifications: public room title, private chat = sender."""
    return room.title if room.public else (sender.username or "System")


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
                room_to_leave = await self.repo.get_room(room_id_to_leave)
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
        for msg_data in messages_list:
            upvotes = msg_data['upvotes']
            downvotes = msg_data['downvotes']
            edited = msg_data['edited']
            attachments = msg_data['attachments']

            try:
                data = format_chat_message(
                    room_id=room_id,
                    user_id=msg_data["sender_id"],
                    anonymous=msg_data['anonymous'],
                    message=msg_data['text'],
                    message_id=msg_data['id'],
                    new=False,
                    upvotes=upvotes,
                    downvotes=downvotes,
                    edited=edited,
                    date=msg_data['time'],
                    latest_date=msg_data['time'],
                    attachments=attachments,
                    reply_to=msg_data.get('reply_to'),
                    reactions={'bulb': msg_data.get('bulb_count', 0), 'question': msg_data.get('question_count', 0)},
                    read_by=msg_data.get('read_by', []),
                    upvoters=msg_data.get('upvoters'),
                    downvoters=msg_data.get('downvoters'),
                )
            except TypeError:
                data = None
                continue

            to_send.append(self.format_chat_message_data_batch(data, users_dict, user_votes_dict))

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
        for msg_data in messages_list:
            try:
                data = format_chat_message(
                    room_id=room_id,
                    user_id=msg_data["sender_id"],
                    anonymous=msg_data['anonymous'],
                    message=msg_data['text'],
                    message_id=msg_data['id'],
                    new=False,
                    upvotes=msg_data['upvotes'],
                    downvotes=msg_data['downvotes'],
                    edited=msg_data['edited'],
                    date=msg_data['time'],
                    latest_date=msg_data['time'],
                    attachments=msg_data['attachments'],
                    reply_to=msg_data.get('reply_to'),
                    reactions={'bulb': msg_data.get('bulb_count', 0), 'question': msg_data.get('question_count', 0)},
                    read_by=msg_data.get('read_by', []),
                    upvoters=msg_data.get('upvoters'),
                    downvoters=msg_data.get('downvoters'),
                )
            except TypeError:
                continue

            to_send.append(self.format_chat_message_data_batch(data, users_dict, user_votes_dict))

        proxy.send_json({'replace_messages': True, 'room_id': str(room_id), 'messages': to_send})

    @handlers.register("send")
    async def send_message_to_room(self, proxy: HandledMessage, room_id, message, is_anonymous, attachments, reply_to_id=None, temp_id=None):
        if int(room_id) not in self.rooms.items():
            raise ClientError("ROOM_ACCESS_DENIED")

        for key, value in attachments.items():
            if key not in ('images',):
                raise ClientError("BAD_ATTACHMENT_TYPE")
            for filename in value:
                if not os.path.exists(f"{settings.BASE_DIR}/media/uploads/{filename}"):
                    raise ClientError("FILE_NOT_FOUND")

        message_clean = sanitize(message, linkify=False)
        message_clean = re.sub(r'(<br\s*/?>)+$', '', message_clean).rstrip()

        if not message_clean.strip().replace('<br>', '').replace('<br/>', '') and not attachments:
            raise ClientError("EMPTY_MESSAGE")

        sender = self.scope["user"]
        room = await self.repo.get_room_or_error(room_id)

        if not room.public and is_anonymous:
            raise ClientError("ANONYMOUS_IN_PRIVATE")

        if not await self.repo.can_post_in_room(room):
            raise ClientError("ACCESS_DENIED")

        reply_to_data = None
        if reply_to_id:
            try:
                reply_to_id = int(reply_to_id)
            except (TypeError, ValueError):
                raise ClientError("MESSAGE_INVALID") from None
            reply_to_data = await self.repo.get_reply_to_data(reply_to_id, room.id)
        else:
            reply_to_id = None

        msg = Message(sender=sender, text=message_clean, room=room, anonymous=is_anonymous, reply_to_id=reply_to_id)
        message_id = await self.repo.save_message(msg)
        msg.id = message_id

        await self.repo.save_attachments(message_id, attachments)

        # Broadcast directly (not via proxy) so subscribers receive the message before this handler returns.
        # Per-recipient bookkeeping (unread state, push notifications) runs in a background task.
        await self.channel_layer.group_send(
            room.group_name,
            format_chat_message(
                room_id=room_id,
                user_id=sender.id,
                anonymous=is_anonymous,
                message=message_clean,
                message_id=message_id,
                upvotes=0,
                downvotes=0,
                new=True,
                edited=False,
                date=msg.time,
                latest_date=msg.time,
                attachments=attachments,
                reply_to=reply_to_data,
                reactions={'bulb': 0, 'question': 0},
                temp_id=temp_id,
            ),
        )

        mentioned_usernames = extract_mentions(message_clean)
        mentioned_users = await self.repo.get_mentioned_users(room, mentioned_usernames) if mentioned_usernames else []
        mentioned_user_ids = {u.id for u in mentioned_users}
        asyncio.create_task(self._post_send_processing(sender, room, msg, message_id, mentioned_user_ids))
        asyncio.create_task(self._notify_mentions(sender, room, msg, mentioned_users))

    async def _post_send_processing(self, sender, room, msg, message_id, mentioned_user_ids=None):
        try:
            if mentioned_user_ids is None:
                mentioned_user_ids = set()
            room_members = await database_sync_to_async(lambda: list(room.allowed.all()))()
            other_members = [m for m in room_members if m.id != sender.id]
            if not other_members:
                return

            other_member_ids = [m.id for m in other_members]
            online_ids = ChatConsumer.online_registry.get_online()
            offline_ids = [mid for mid in other_member_ids if mid not in online_ids]
            if offline_ids:
                await database_sync_to_async(lambda: Room.seen_by.through.objects.filter(room_id=room.id, user_id__in=offline_ids).delete())()
                await database_sync_to_async(cache.delete_many)([CHAT_UNREAD_CACHE_KEY.format(user_id=uid) for uid in offline_ids])

            membership_prefs = await database_sync_to_async(lambda: Room.get_membership_preferences_bulk(room.id, other_member_ids))()

            proxy = HandledMessage()
            author = "Anonymous" if msg.anonymous else (sender.username or "System")
            notify_room_name = _room_notification_name(room, sender)
            notification = _build_chat_notification(author, room.id, notify_room_name)
            for member in other_members:
                prefs = membership_prefs.get(member.id, {'seen': False, 'muted': True})
                consumer = ChatConsumer.online_registry.get_consumer(member)
                is_present = bool(consumer) and consumer.rooms.present(room)

                is_mentioned = member.id in mentioned_user_ids
                # Notify always (foreground/background/in-room) unless muted or already handled by mention flow.
                if not prefs['muted'] and not is_mentioned:
                    asyncio.create_task(self.send_push_notification_async(proxy, member, msg, room.id, notify_room_name))
                    # Show a real OS notification via the shared WebSocket connection too, so
                    # it appears immediately even while the tab is in the foreground (FCM's
                    # foreground routing is unreliable across browsers). Push (FCM) still
                    # covers the case where the tab/browser is fully closed.
                    log.debug(f"{NOTIF_LOG_TAG} group_send chat.notification notification_id={notification['notification_id']} to user_{member.id} for message {message_id} (present={is_present})")
                    await self.channel_layer.group_send(f"user_{member.id}", {"type": "chat.notification", "room_id": room.id, "notification": {**notification, "room_id": room.id}})

                if not consumer:
                    continue

                if is_present:
                    continue

                if prefs['seen']:
                    await consumer.repo.unsee_room(room)
                    await consumer.push_unread_count()
                    await consumer.send_unsee_room(proxy=proxy, room=room)

            await self._dispatch_proxy(proxy)
        except Exception as e:
            log.error(f"Error in post-send processing for message {message_id}: {e}", exc_info=True)

    async def _notify_mentions(self, sender, room, msg, mentioned_users):
        """Notify users explicitly mentioned with @username in the message."""
        try:
            if not mentioned_users:
                return
            for user in mentioned_users:
                if user.id == sender.id:
                    continue
                asyncio.create_task(self._send_mention_notification(sender, room, user, msg))
        except Exception as e:
            log.error(f"{NOTIF_LOG_TAG} Error in mention notification for message {msg.id}: {e}", exc_info=True)

    async def _send_mention_notification(self, sender, room, user, msg):
        """Send a WebSocket notification and a push for a single mention."""
        try:
            author = "Anonymous" if msg.anonymous else (sender.username or "System")
            notify_room_name = _room_notification_name(room, sender)
            notification = _build_chat_notification(author, room.id, notify_room_name)

            log.debug(f"{NOTIF_LOG_TAG} group_send chat.mention notification_id={notification['notification_id']} to user_{user.id} for message {msg.id}")
            # Show a real OS notification via the shared WebSocket connection too, so it
            # appears immediately even while the tab is in the foreground (push/FCM still
            # covers the case where the tab/browser is fully closed).
            await self.channel_layer.group_send(f"user_{user.id}", {"type": "chat.mention", "room_id": room.id, "notification": {**notification, "room_id": room.id}})

            # Push notification (bypasses room mute because it is a direct mention).
            success = await self.repo.send_push_notification_sync(user, notification['title'], notification['body'], notification['click_action'], room.id, room_name=notify_room_name)
            if success:
                log.info(f"{NOTIF_LOG_TAG} Mention notification sent to user {user.id} for message {msg.id} (ws notification_id={notification['notification_id']})")
            else:
                log.debug(f"{NOTIF_LOG_TAG} No push devices active for mention to user {user.id} (ws notification_id={notification['notification_id']})")
        except Exception as e:
            log.error(f"{NOTIF_LOG_TAG} Error sending mention notification to user {user.id}: {e}", exc_info=True)

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
            room = await self.repo.get_room(room_id)
        except ClientError:
            return
        if not await self.repo.room_is_seen(room):
            await self.repo.see_room(room)
            await self.push_unread_count()

    @handlers.register("room-unseen")
    async def handle_unseen_room(self, proxy: HandledMessage, room_id):
        try:
            room = await self.repo.get_room(room_id)
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
        room = await self.repo.get_room(room_id)
        new_ids = await self.repo.mark_messages_read_bulk(message_ids, room.id)
        for message_id in new_ids:
            read_by = await self.repo.get_read_by_data(message_id)
            proxy.group_send(room.group_name, {"type": "chat.read", "messages_read": {"message_id": message_id, "read_by": read_by}})

    @handlers.register("edit-message")
    async def handle_edit_message(self, proxy: HandledMessage, message_id: int, new_message: str = None, attachments: dict = None, removed_attachments: list = None):
        message = await self.repo.get_message(message_id)
        if await self.repo.get_message_sender(message) != self.scope['user']:
            return

        if new_message is None:
            new_message = message.text
        else:
            new_message = sanitize(new_message, linkify=False)
            new_message = re.sub(r'(<br\s*/?>)+$', '', new_message).rstrip()

        if attachments:
            for key, value in attachments.items():
                if key not in ('images',):
                    raise ClientError("BAD_ATTACHMENT_TYPE")
                for filename in value:
                    if not os.path.exists(f"{settings.BASE_DIR}/media/uploads/{filename}"):
                        raise ClientError("FILE_NOT_FOUND")

        if removed_attachments:
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
            timestamp = int(datetime.now().timestamp()) * 1000

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

    @helper_method
    async def send_notification(self, proxy: HandledMessage, message_id):
        message = await self.repo.get_message(message_id)
        sender = await self.repo.get_message_sender(message_id)
        proxy.send_json({"notification": {'title': "Anonymous" if message.anonymous else sender.username, 'body': "New message", 'link': None, 'room_id': (await self.repo.get_room_by_message(message.id)).id}})

    @helper_method
    async def send_unsee_room(self, proxy, room):
        if self.rooms.present(room):
            return
        proxy.send_json({"unsee_room": room.id})

    @helper_method
    async def send_push_notification_async(self, proxy, user, message, room_id, room_name=""):
        try:
            if await self.repo.user_has_muted_room(user.id, room_id):
                return
            author = "System" if message.sender is None else ("Anonymous" if message.anonymous else message.sender.username)
            notification = _build_chat_notification(author, room_id, room_name)
            success = await self.repo.send_push_notification_sync(
                user=user, title=notification['title'], body=notification['body'], deep_link=notification['click_action'], room_id=room_id, room_name=room_name or ""
            )
            if success:
                log.info(f"{NOTIF_LOG_TAG} Push notification sent to user {user.id} for message {message.id} (ws notification_id={notification['notification_id']})")
            else:
                log.debug(f"{NOTIF_LOG_TAG} No push devices active for user {user.id} (ws notification_id={notification['notification_id']})")
        except Exception as e:
            log.error(f"{NOTIF_LOG_TAG} Error sending push notification: {e}")

    async def handle_leave_room(self, room):
        self.rooms.leave(room.id)
        await self.channel_layer.group_discard(room.group_name, self.channel_name)

    async def format_chat_message_data(self, event):
        user = await self.repo.get_user_by_id(event["user_id"])
        vote = await self.repo.get_vote(event['message_id'])
        vote_value = vote.vote if vote is not None else None
        avatar_url = get_avatar_url(user)
        return build_chat_message_payload(event, user=user, vote_value=vote_value, current_user=self.scope['user'], avatar_url=avatar_url)

    def format_chat_message_data_batch(self, event, users_dict, user_votes_dict, user_reactions_dict=None):
        user = users_dict.get(event["user_id"])
        vote_value = user_votes_dict.get(event["message_id"])
        your_reactions = (user_reactions_dict or {}).get(event["message_id"], [])
        avatar_url = get_avatar_url(user)
        return build_chat_message_payload(event, user=user, vote_value=vote_value, current_user=self.scope['user'], your_reactions=your_reactions, avatar_url=avatar_url)

    ###########################################################
    # Handlers for messages sent over the channel layer       #
    ###########################################################

    async def chat_message(self, event):
        message = await self.format_chat_message_data(event)
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
