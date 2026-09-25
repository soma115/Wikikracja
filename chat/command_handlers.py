"""Application handlers for chat WebSocket commands."""

import re
from dataclasses import dataclass, field

from channels.db import database_sync_to_async
from django.utils import timezone

from core.presence import PRESENCE_GROUP
from core.richtext import sanitize
from zzz.templatetags.citizen_filters import user_display_name

from .exceptions import ClientError
from .reactions import ChatReactionService
from .serializers import build_chat_message_payloads
from .services import get_avatar_url, send_message
from .utils import get_upload_path


@dataclass
class CommandResult:
    responses: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class CommandSpec:
    handler_name: str
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()


COMMAND_SPECS = {
    'join': CommandSpec('join', ('room_id',)),
    'fetch-messages': CommandSpec('fetch_messages', ('room_id',), ('sort_by', 'order', 'popular_only')),
    'send': CommandSpec('send', ('room_id', 'message', 'is_anonymous', 'attachments'), ('reply_to_id', 'temp_id')),
    'room-seen': CommandSpec('mark_room_seen', ('room_id',)),
    'room-unseen': CommandSpec('mark_room_unseen', ('room_id',)),
    'leave': CommandSpec('leave', ('room_id',)),
    'get-online-users': CommandSpec('get_online_users', ()),
    'message-add-vote': CommandSpec('add_vote', ('vote', 'message_id')),
    'message-remove-vote': CommandSpec('remove_vote', ('vote', 'message_id')),
    'message-react': CommandSpec('react', ('reaction', 'message_id')),
    'message-mark-read': CommandSpec('mark_read', ('message_id',)),
    'messages-mark-read-bulk': CommandSpec('mark_read_bulk', ('message_ids', 'room_id')),
    'get-message-history': CommandSpec('get_message_history', ('message_id',)),
    'edit-message': CommandSpec('edit_message', ('message_id',), ('new_message', 'attachments', 'removed_attachments')),
    'toggle-notifications': CommandSpec('toggle_notifications', ('room_id', 'enabled')),
    'get-notifications-data': CommandSpec('get_notifications_data', ()),
    'presence-heartbeat': CommandSpec('presence_heartbeat', ()),
}


def build_message_payloads(batch_data, current_user):
    """Backward-compatible wrapper around the canonical batch serializer."""
    return build_chat_message_payloads(batch_data, current_user, get_avatar_url)


class ChatCommandHandlers:
    """Execute chat use cases independently from command parsing and dispatch."""

    def __init__(self, consumer, online_registry):
        self.consumer = consumer
        self.online_registry = online_registry

    @property
    def room_repo(self):
        return getattr(self.consumer, 'room_repo', self.consumer.repo)

    @property
    def reaction_service(self):
        return ChatReactionService(self.consumer.repo)

    @staticmethod
    def handles(command):
        return command in COMMAND_SPECS

    async def dispatch(self, command, content):
        spec = COMMAND_SPECS[command]
        missing = [name for name in spec.required if content.get(name) is None]
        if missing:
            raise ClientError('DATA_MISSING')
        kwargs = {name: content[name] for name in spec.required}
        kwargs.update({name: content[name] for name in spec.optional if content.get(name) is not None})
        return await getattr(self, spec.handler_name)(**kwargs)

    async def join(self, room_id):
        room = await self.room_repo.get_room_or_error(room_id)
        for joined_room_id in self.consumer.rooms.items():
            try:
                joined_room = await self.room_repo.get_room_or_error(joined_room_id)
            except ClientError:
                self.consumer.rooms.leave(joined_room_id)
                continue
            await self._leave_room(joined_room)

        self.consumer.rooms.join(room_id)
        await self.consumer.channel_layer.group_add(room.group_name, self.consumer.channel_name)
        responses = [
            {'join': str(room.id), 'title': room.title, 'public': room.public, 'notifications': not await self.room_repo.has_muted_room(room.id), 'can_post': await self.room_repo.can_post_in_room(room)}
        ]
        batch = await self.consumer.repo.get_recent_messages_batch(room_id, self.consumer.scope['user'].id, limit=100, include_voters=room.source_app == 'tasks')
        messages = build_message_payloads(batch, self.consumer.scope['user'])
        if messages:
            responses.append({'messages': messages})
        return CommandResult(responses)

    async def fetch_messages(self, room_id, sort_by='date', order='desc', popular_only=False):
        room = await self.room_repo.get_room_or_error(room_id)
        sort_by = sort_by if sort_by in ('date', 'likes', None) else 'date'
        order = order if order in ('asc', 'desc', None) else 'desc'
        batch = await self.consumer.repo.get_recent_messages_batch(
            room_id, self.consumer.scope['user'].id, limit=100, sort_by=sort_by, order=order, popular_only=bool(popular_only), include_voters=room.source_app == 'tasks'
        )
        return CommandResult([{'replace_messages': True, 'room_id': str(room_id), 'messages': build_message_payloads(batch, self.consumer.scope['user'])}])

    async def send(self, room_id, message, is_anonymous, attachments, reply_to_id=None, temp_id=None):
        try:
            room_id = int(room_id)
        except (TypeError, ValueError):
            raise ClientError('ROOM_INVALID') from None
        if room_id not in self.consumer.rooms.items():
            raise ClientError('ROOM_ACCESS_DENIED')
        attachments = self._validate_attachments(attachments)
        room = await self.room_repo.get_room_or_error(room_id)
        await send_message(
            room,
            message,
            sender=self.consumer.scope['user'],
            anonymous=is_anonymous,
            attachments=attachments,
            reply_to_id=reply_to_id,
            temp_id=temp_id,
            linkify=False,
            channel_layer=self.consumer.channel_layer,
            online_registry=self.online_registry,
            background=True,
        )
        return CommandResult()

    async def mark_room_seen(self, room_id):
        try:
            room = await self.room_repo.get_room_or_error(room_id)
        except ClientError:
            return CommandResult()
        if not await self.room_repo.room_is_seen(room):
            await self.room_repo.see_room(room)
            await self.consumer.channel_layer.group_send(f"user_{self.consumer.scope['user'].id}", {'type': 'chat.room_unread', 'room_id': room.id, 'count': 0})
            await self.consumer.push_unread_count()
        return CommandResult()

    async def mark_room_unseen(self, room_id):
        try:
            room = await self.room_repo.get_room_or_error(room_id)
        except ClientError:
            return CommandResult()
        await self.room_repo.unsee_room(room)
        await self.consumer.push_unread_count()
        return CommandResult()

    async def leave(self, room_id):
        room = await self.room_repo.get_room_or_error(room_id)
        await self._leave_room(room)
        return CommandResult([{'leave': str(room.id)}])

    async def get_online_users(self):
        scoped_user = self.consumer.scope['user']
        online_user_ids = [user_id for user_id in self.online_registry.get_online() if user_id != scoped_user.id]
        rooms = await self.room_repo.find_private_rooms_for_user_pairs(scoped_user, online_user_ids)
        return CommandResult([{'online_data': [{'user_id': user_id, 'room_id': rooms[user_id].id, 'online': True} for user_id in online_user_ids if user_id in rooms]}])

    async def add_vote(self, vote, message_id):
        counts = await self.reaction_service.add_vote(vote, message_id)
        if counts is None:
            return CommandResult()
        upvotes, downvotes = counts
        await self._broadcast_vote_update(message_id, vote, upvotes, downvotes, add=True)
        return CommandResult()

    async def remove_vote(self, vote, message_id):
        upvotes, downvotes = await self.reaction_service.remove_vote(vote, message_id)
        await self._broadcast_vote_update(message_id, vote, upvotes, downvotes, add=False)
        return CommandResult()

    async def _broadcast_vote_update(self, message_id, vote, upvotes, downvotes, add):
        room = await self.consumer.repo.get_room_by_message(message_id)
        update_votes = {'message_id': message_id, 'upvotes': upvotes, 'downvotes': downvotes, 'user_id': self.consumer.scope['user'].id, 'vote': vote, 'add': add}
        if room.source_app == 'tasks':
            update_votes.update(await self.consumer.repo.get_vote_voters(message_id))
        await self.consumer.channel_layer.group_send(room.group_name, {'type': 'chat.vote', 'update_votes': update_votes})

    async def react(self, reaction, message_id):
        added, counts = await self.reaction_service.toggle_reaction(reaction, message_id)
        room = await self.consumer.repo.get_room_by_message(message_id)
        await self.consumer.channel_layer.group_send(
            room.group_name, {'type': 'chat.reaction', 'update_reactions': {'message_id': message_id, 'reaction': reaction, 'counts': counts, 'user_id': self.consumer.scope['user'].id, 'added': added}}
        )
        return CommandResult()

    async def mark_read(self, message_id):
        await self.consumer.repo.mark_message_read(message_id)
        read_by = await self.consumer.repo.get_read_by_data(message_id)
        room = await self.consumer.repo.get_room_by_message(message_id)
        await self.consumer.channel_layer.group_send(room.group_name, {'type': 'chat.read', 'messages_read': {'message_id': message_id, 'read_by': read_by}})
        return CommandResult()

    async def mark_read_bulk(self, message_ids, room_id):
        room = await self.room_repo.get_room_or_error(room_id)
        new_ids = await self.consumer.repo.mark_messages_read_bulk(message_ids, room.id)
        for message_id in new_ids:
            read_by = await self.consumer.repo.get_read_by_data(message_id)
            await self.consumer.channel_layer.group_send(room.group_name, {'type': 'chat.read', 'messages_read': {'message_id': message_id, 'read_by': read_by}})
        return CommandResult()

    async def get_message_history(self, message_id):
        states = await self.consumer.repo.get_message_states(message_id)
        return CommandResult([{'message_history': states}])

    async def toggle_notifications(self, room_id, enabled):
        if enabled:
            await self.room_repo.unmute_room(room_id)
        else:
            await self.room_repo.mute_room(room_id)
        return CommandResult()

    async def get_notifications_data(self):
        rooms = await self.room_repo.get_rooms_with_notifications_enabled()
        return CommandResult([{'rooms': [room.id for room in rooms]}])

    async def presence_heartbeat(self):
        update = await self.consumer.record_presence('app')
        if update:
            await self.consumer.channel_layer.group_send(PRESENCE_GROUP, {'type': 'presence.update', **update})
        return CommandResult()

    async def send_online_update(self, is_online):
        updated_user = self.consumer.scope['user']
        for room in await self.room_repo.find_rooms_with(updated_user):
            other_user = await database_sync_to_async(room.get_other)(updated_user)
            if not self.online_registry.is_online(other_user):
                continue
            target = self.online_registry.get_consumer(other_user)
            await target.send_json({'online_data': [{'user_id': updated_user.id, 'room_id': room.id, 'online': is_online}]})

    async def edit_message(self, message_id, new_message=None, attachments=None, removed_attachments=None):
        message = await self.consumer.repo.get_message(message_id)
        if await self.consumer.repo.get_message_sender(message) != self.consumer.scope['user']:
            raise ClientError('ACCESS_DENIED')

        if new_message is None:
            new_message = message.text
        else:
            new_message = re.sub(r'(<br\\s*/?>)+$', '', sanitize(new_message, linkify=False)).rstrip()

        attachments = self._validate_edit_attachments(attachments)
        if removed_attachments is not None and not isinstance(removed_attachments, (list, tuple)):
            raise ClientError('BAD_ATTACHMENT_TYPE')
        if removed_attachments:
            await self.consumer.repo.remove_attachments(message_id, removed_attachments)
        if attachments:
            await self.consumer.repo.save_attachments(message_id, attachments)

        updated_attachments = await self.consumer.repo.load_attachments(message_id)
        text_changed = message.text != new_message
        attachments_changed = bool(attachments) or bool(removed_attachments)
        if not text_changed and not attachments_changed:
            return CommandResult()

        room = await self.consumer.repo.get_room_by_message(message_id)
        if text_changed:
            state = await self.consumer.repo.edit_message_and_history(message_id, new_message)
            timestamp = int(state.time.timestamp()) * 1000
        else:
            timestamp = int(timezone.now().timestamp()) * 1000
        is_last = await self.consumer.repo.is_last_message_in_room(message_id, room.id)
        await self.consumer.channel_layer.group_send(
            room.group_name,
            {
                'type': 'chat.edit',
                'edit_message': {
                    'message_id': message_id,
                    'room_id': room.id,
                    'user_id': self.consumer.scope['user'].id,
                    'username': self.consumer.scope['user'].username,
                    'display_name': 'Anonymous' if message.anonymous else user_display_name(self.consumer.scope['user']),
                    'anonymous': message.anonymous,
                    'is_last_message': is_last,
                    'text': new_message,
                    'timestamp': timestamp,
                    'attachments': updated_attachments,
                },
            },
        )
        return CommandResult()

    @staticmethod
    def _validate_edit_attachments(attachments):
        if attachments is None:
            return {}
        if not isinstance(attachments, dict):
            raise ClientError('BAD_ATTACHMENT_TYPE')
        for attachment_type, filenames in attachments.items():
            if attachment_type != 'images' or not isinstance(filenames, (list, tuple)):
                raise ClientError('BAD_ATTACHMENT_TYPE')
            for filename in filenames:
                if not isinstance(filename, str):
                    raise ClientError('BAD_ATTACHMENT_TYPE')
                path = get_upload_path(filename)
                if path is None or not path.is_file():
                    raise ClientError('FILE_NOT_FOUND')
        return attachments

    async def _leave_room(self, room):
        self.consumer.rooms.leave(room.id)
        await self.consumer.channel_layer.group_discard(room.group_name, self.consumer.channel_name)

    @staticmethod
    def _validate_attachments(attachments):
        if attachments is None:
            return {}
        if not isinstance(attachments, dict):
            raise ClientError('BAD_ATTACHMENT_TYPE')
        for attachment_type, filenames in attachments.items():
            if attachment_type != 'images' or not isinstance(filenames, (list, tuple)):
                raise ClientError('BAD_ATTACHMENT_TYPE')
            if any(not isinstance(filename, str) for filename in filenames):
                raise ClientError('BAD_ATTACHMENT_TYPE')
        return attachments
