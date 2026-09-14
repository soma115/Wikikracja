from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from django.test import SimpleTestCase

from chat.command_handlers import ChatCommandHandlers, CommandResult
from chat.consumers import ChatConsumer
from chat.exceptions import ClientError


class ChatCommandHandlersTest(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=7, username='handler-user', get_full_name=lambda: '')
        self.repo = SimpleNamespace(
            get_room_or_error=AsyncMock(),
            has_muted_room=AsyncMock(return_value=False),
            can_post_in_room=AsyncMock(return_value=True),
            get_recent_messages_batch=AsyncMock(return_value={'messages': [], 'users': {}, 'user_votes': {}}),
            find_private_rooms_for_user_pairs=AsyncMock(return_value={}),
            find_rooms_with=AsyncMock(return_value=[]),
            room_is_seen=AsyncMock(return_value=False),
            see_room=AsyncMock(),
            unsee_room=AsyncMock(),
            mark_message_read=AsyncMock(),
            get_read_by_data=AsyncMock(return_value=[{'user_id': 8}]),
            get_room_by_message=AsyncMock(),
            mark_messages_read_bulk=AsyncMock(return_value=[4, 5]),
            get_message_states=AsyncMock(return_value=[{'text': 'old'}]),
            unmute_room=AsyncMock(),
            mute_room=AsyncMock(),
            get_rooms_with_notifications_enabled=AsyncMock(return_value=[SimpleNamespace(id=3)]),
        )
        self.rooms = MagicMock()
        self.rooms.items.return_value = []
        self.channel_layer = SimpleNamespace(group_add=AsyncMock(), group_discard=AsyncMock(), group_send=AsyncMock())
        self.consumer = SimpleNamespace(
            repo=self.repo, rooms=self.rooms, channel_layer=self.channel_layer, channel_name='channel-1', scope={'user': self.user}, push_unread_count=AsyncMock(), record_presence=AsyncMock()
        )
        self.online_registry = MagicMock()
        self.handlers = ChatCommandHandlers(self.consumer, self.online_registry)

    async def test_dispatch_rejects_missing_required_data(self):
        with self.assertRaises(ClientError) as raised:
            await self.handlers.dispatch('join', {})
        self.assertEqual(raised.exception.code, 'DATA_MISSING')

    async def test_join_returns_metadata_and_messages_from_shared_builder(self):
        room = SimpleNamespace(id=3, group_name='room-3', title='Room', public=True, source_app='')
        self.repo.get_room_or_error.return_value = room
        with patch('chat.command_handlers.build_message_payloads', return_value=[{'message_id': 1}]) as build:
            result = await self.handlers.join(room.id)

        self.assertEqual(result.responses[0]['join'], '3')
        self.assertEqual(result.responses[1], {'messages': [{'message_id': 1}]})
        self.channel_layer.group_add.assert_awaited_once_with('room-3', 'channel-1')
        build.assert_called_once()

    async def test_fetch_normalizes_sort_options_and_uses_shared_builder(self):
        room = SimpleNamespace(id=3, source_app='')
        self.repo.get_room_or_error.return_value = room
        with patch('chat.command_handlers.build_message_payloads', return_value=[]) as build:
            result = await self.handlers.fetch_messages(3, sort_by='invalid', order='invalid', popular_only=1)

        self.repo.get_recent_messages_batch.assert_awaited_once_with(3, self.user.id, limit=100, sort_by='date', order='desc', popular_only=True, include_voters=False)
        self.assertEqual(result.responses, [{'replace_messages': True, 'room_id': '3', 'messages': []}])
        build.assert_called_once()

    async def test_send_validates_joined_room_and_delegates_use_case(self):
        room = SimpleNamespace(id=3)
        self.rooms.items.return_value = [3]
        self.repo.get_room_or_error.return_value = room
        with patch('chat.command_handlers.send_message', new_callable=AsyncMock) as send:
            result = await self.handlers.send('3', 'Hello', False, {'images': ['image.webp']})

        self.assertEqual(result, CommandResult())
        send.assert_awaited_once()
        self.assertEqual(send.await_args.args[:2], (room, 'Hello'))

    async def test_leave_removes_room_membership_and_returns_legacy_response(self):
        room = SimpleNamespace(id=3, group_name='room-3')
        self.repo.get_room_or_error.return_value = room
        self.rooms.items.return_value = [3]

        result = await self.handlers.leave(3)

        self.rooms.leave.assert_called_once_with(3)
        self.channel_layer.group_discard.assert_awaited_once_with('room-3', 'channel-1')
        self.assertEqual(result.responses, [{'leave': '3'}])

    async def test_get_online_users_returns_only_users_with_private_rooms(self):
        room = SimpleNamespace(id=9)
        self.online_registry.get_online.return_value = [self.user.id, 8, 12]
        self.repo.find_private_rooms_for_user_pairs.return_value = {8: room}

        result = await self.handlers.get_online_users()

        self.repo.find_private_rooms_for_user_pairs.assert_awaited_once_with(self.user, [8, 12])
        self.assertEqual(result.responses, [{'online_data': [{'user_id': 8, 'room_id': 9, 'online': True}]}])

    async def test_send_online_update_delivers_directly_to_other_user(self):
        other_user = SimpleNamespace(id=8)
        target = SimpleNamespace(send_json=AsyncMock())
        room = SimpleNamespace(id=9, get_other=lambda user: other_user)
        self.repo.find_rooms_with.return_value = [room]
        self.online_registry.is_online.return_value = True
        self.online_registry.get_consumer.return_value = target

        def run_inline(function):
            async def call_inline(*args):
                return function(*args)

            return call_inline

        with patch('chat.command_handlers.database_sync_to_async', side_effect=run_inline):
            await self.handlers.send_online_update(True)

        target.send_json.assert_awaited_once_with({'online_data': [{'user_id': self.user.id, 'room_id': room.id, 'online': True}]})

    async def test_add_vote_broadcasts_task_voter_names(self):
        room = SimpleNamespace(id=3, group_name='room-3', source_app='tasks')
        self.repo.get_vote = AsyncMock(return_value=None)
        self.repo.add_vote = AsyncMock(return_value=(2, 1))
        self.repo.get_room_by_message = AsyncMock(return_value=room)
        self.repo.get_vote_voters = AsyncMock(return_value={'upvoters': ['voter'], 'downvoters': []})

        await self.handlers.add_vote('upvote', 4)

        self.channel_layer.group_send.assert_awaited_once_with(
            'room-3', {'type': 'chat.vote', 'update_votes': {'message_id': 4, 'upvotes': 2, 'downvotes': 1, 'user_id': self.user.id, 'vote': 'upvote', 'add': True, 'upvoters': ['voter'], 'downvoters': []}}
        )

    async def test_react_rejects_unknown_reaction(self):
        with self.assertRaises(ClientError) as raised:
            await self.handlers.react('heart', 4)
        self.assertEqual(raised.exception.code, 'INVALID_REACTION')

    async def test_mark_read_broadcasts_readers_to_message_room(self):
        room = SimpleNamespace(id=3, group_name='room-3')
        self.repo.get_room_by_message.return_value = room

        await self.handlers.mark_read(4)

        self.repo.mark_message_read.assert_awaited_once_with(4)
        self.channel_layer.group_send.assert_awaited_once_with('room-3', {'type': 'chat.read', 'messages_read': {'message_id': 4, 'read_by': [{'user_id': 8}]}})

    async def test_mark_read_bulk_broadcasts_only_new_read_rows(self):
        room = SimpleNamespace(id=3, group_name='room-3')
        self.repo.get_room_or_error.return_value = room

        await self.handlers.mark_read_bulk([4, 5], 3)

        self.assertEqual(self.channel_layer.group_send.await_count, 2)
        self.assertEqual(
            [call.args for call in self.channel_layer.group_send.await_args_list],
            [
                ('room-3', {'type': 'chat.read', 'messages_read': {'message_id': 4, 'read_by': [{'user_id': 8}]}}),
                ('room-3', {'type': 'chat.read', 'messages_read': {'message_id': 5, 'read_by': [{'user_id': 8}]}}),
            ],
        )

    async def test_get_message_history_returns_legacy_response(self):
        result = await self.handlers.get_message_history(4)
        self.assertEqual(result.responses, [{'message_history': [{'text': 'old'}]}])

    async def test_toggle_notifications_delegates_mute_state(self):
        await self.handlers.toggle_notifications(3, True)
        self.repo.unmute_room.assert_awaited_once_with(3)
        self.repo.mute_room.assert_not_awaited()

        await self.handlers.toggle_notifications(3, False)
        self.repo.mute_room.assert_awaited_once_with(3)

    async def test_get_notifications_data_returns_enabled_room_ids(self):
        result = await self.handlers.get_notifications_data()
        self.assertEqual(result.responses, [{'rooms': [3]}])

    async def test_presence_heartbeat_broadcasts_changed_presence(self):
        update = {'user_id': self.user.id, 'status': 'green', 'source': 'app', 'timestamp': '2026-09-14T01:00:00Z'}
        self.consumer.record_presence.return_value = update

        await self.handlers.presence_heartbeat()

        self.consumer.record_presence.assert_awaited_once_with('app')
        self.channel_layer.group_send.assert_awaited_once_with('presence', {'type': 'presence.update', **update})

    async def test_edit_message_saves_history_and_broadcasts_legacy_payload(self):
        message = SimpleNamespace(text='Old', anonymous=False)
        room = SimpleNamespace(id=3, group_name='room-3')
        state = SimpleNamespace(time=SimpleNamespace(timestamp=lambda: 1000))
        self.repo.get_message = AsyncMock(return_value=message)
        self.repo.get_message_sender = AsyncMock(return_value=self.user)
        self.repo.load_attachments = AsyncMock(return_value={'images': []})
        self.repo.get_room_by_message = AsyncMock(return_value=room)
        self.repo.edit_message_and_history = AsyncMock(return_value=state)
        self.repo.is_last_message_in_room = AsyncMock(return_value=True)

        await self.handlers.edit_message(4, new_message='New')

        self.repo.edit_message_and_history.assert_awaited_once_with(4, 'New')
        group, event = self.channel_layer.group_send.await_args.args
        self.assertEqual(group, 'room-3')
        self.assertEqual(event['type'], 'chat.edit')
        self.assertEqual(event['edit_message']['text'], 'New')
        self.assertEqual(event['edit_message']['timestamp'], 1000000)

    async def test_edit_message_rejects_missing_attachment_file(self):
        message = SimpleNamespace(text='Old', anonymous=False)
        self.repo.get_message = AsyncMock(return_value=message)
        self.repo.get_message_sender = AsyncMock(return_value=self.user)

        with self.assertRaises(ClientError) as raised:
            await self.handlers.edit_message(4, attachments={'images': ['missing.webp']})

        self.assertEqual(raised.exception.code, 'FILE_NOT_FOUND')

    async def test_mark_room_seen_updates_room_and_global_count(self):
        room = SimpleNamespace(id=3)
        self.repo.get_room_or_error.return_value = room

        await self.handlers.mark_room_seen(room.id)

        self.repo.see_room.assert_awaited_once_with(room)
        self.channel_layer.group_send.assert_awaited_once_with(f'user_{self.user.id}', {'type': 'chat.room_unread', 'room_id': room.id, 'count': 0})
        self.consumer.push_unread_count.assert_awaited_once()


class ExtractedCommandDispatchTest(SimpleTestCase):
    async def test_receive_json_preserves_trace_id_for_extracted_command(self):
        consumer = ChatConsumer.__new__(ChatConsumer)
        consumer.send_json = AsyncMock()
        with patch('chat.consumers.ChatCommandHandlers.dispatch', new_callable=AsyncMock, return_value=CommandResult([{'join': '3'}, {'messages': [{'message_id': 4}]}])):
            await consumer.receive_json({'command': 'join', 'room_id': 3, '__TRACE_ID': 'trace-1'})

        self.assertEqual(consumer.send_json.await_args_list, [call({'join': '3', '__TRACE_ID': 'trace-1'}), call({'messages': [{'message_id': 4}]})])
