import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from channels.db import database_sync_to_async
from django.core.cache import cache
from django.test import TestCase, override_settings

from chat.consumers import ChatConsumer
from chat.exceptions import ClientError
from chat.models import Message, Room
from chat.services import CHAT_UNREAD_CACHE_KEY, ChatRepository, _send_mention, send_message
from chat.tests.utils import make_user
from chat.utils import HandledMessage
from tasks.models import TaskVote
from tasks.tests.utils import make_task


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PostSendProcessingUnseenTest(TestCase):
    """
    Regression tests for _dispatch_message_notifications: ensures the correct call path
    consumer.repo.unsee_room(room) is used, and that push_unread_count is called iff
    the receiver had previously seen the room.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.push = self.enterContext(patch('core.notifications.send_fcm_to_user_sync', return_value=1))
        self.sender = make_user("sender")
        self.receiver = make_user("receiver")
        self.room = Room.objects.create(title="test-room", public=False)
        self.room.allowed.add(self.sender, self.receiver)

    def _make_receiver_consumer(self):
        consumer = MagicMock(spec=ChatConsumer)
        consumer.scope = {'user': self.receiver}
        consumer.rooms = MagicMock()
        consumer.rooms.present = MagicMock(return_value=False)
        consumer.repo = AsyncMock()
        consumer.repo.unsee_room = AsyncMock()
        consumer.push_unread_count = AsyncMock()
        consumer.send_json = AsyncMock()
        return consumer

    def _make_online_registry(self, consumer):
        registry = MagicMock()
        registry.get_online = MagicMock(return_value=[self.receiver.id])
        registry.get_consumer = MagicMock(return_value=consumer)
        return registry

    async def _run(self, receiver_consumer, text="hello", *, anonymous=False, online=True):
        self.channel_layer = AsyncMock()
        online_registry = self._make_online_registry(receiver_consumer)
        if not online:
            online_registry.get_online.return_value = []
        with patch('chat.services.log') as log:
            await send_message(self.room, text, self.sender, anonymous=anonymous, channel_layer=self.channel_layer, online_registry=online_registry)
        log.error.assert_not_called()
        return self.push

    def _notifications(self):
        return [(call.args[0], call.args[1]) for call in self.channel_layer.group_send.await_args_list if call.args[1]['type'] in ('chat.notification', 'chat.mention')]

    async def test_seen_receiver_gets_unseen_count_and_push(self):
        """Receiver had seen the room — repo.unsee_room, push_unread_count and push must be called."""
        await database_sync_to_async(self.room.seen_by.add)(self.receiver)
        receiver = self._make_receiver_consumer()

        mock_send_push = await self._run(receiver)

        receiver.repo.unsee_room.assert_awaited_once_with(self.room)
        receiver.push_unread_count.assert_awaited_once()
        mock_send_push.assert_called_once()

    async def test_not_seen_receiver_skips_unseen_and_count_but_pushes(self):
        """Receiver had NOT seen the room — repo.unsee_room and push_unread_count must NOT be called, but push is still sent."""
        receiver = self._make_receiver_consumer()

        mock_send_push = await self._run(receiver)

        receiver.repo.unsee_room.assert_not_awaited()
        receiver.push_unread_count.assert_not_awaited()
        mock_send_push.assert_called_once()

    async def test_race_no_consumer_muted_seen_does_not_crash(self):
        """Regression: race condition where online_registry reports member as online
        but get_consumer() returns None (e.g. disconnect between registry check and lookup),
        with muted=True and seen=True. Must not reach consumer.repo (None → AttributeError).
        No push (muted), no crash."""
        await database_sync_to_async(self.room.seen_by.add)(self.receiver)
        await database_sync_to_async(self.room.muted_by.add)(self.receiver)

        with patch('chat.services.log') as mock_log:
            mock_send_push = await self._run(None)  # get_consumer → None

        mock_log.error.assert_not_called()  # bug: crash is swallowed into log.error
        mock_send_push.assert_not_called()  # muted → no push

    async def test_sender_is_never_notified_even_when_self_mentioned(self):
        for text in ('hello', '@sender @receiver'):
            with self.subTest(text=text):
                self.push.reset_mock()
                await self._run(None, text)
                self.push.assert_called_once()
                self.assertEqual(self.push.call_args.args[0], self.receiver)
                self.assertEqual([group for group, _ in self._notifications()], [f'user_{self.receiver.id}'])
        await database_sync_to_async(self.room.allowed.remove)(self.receiver)
        self.push.reset_mock()
        await self._run(None, '@sender')
        self.push.assert_not_called()
        self.assertEqual(self._notifications(), [])

    async def test_send_message_mentions_only_active_allowed_users_once(self):
        inactive = await database_sync_to_async(make_user)('inactive')
        outsider = await database_sync_to_async(make_user)('outsider')
        inactive.is_active = False
        await database_sync_to_async(inactive.save)(update_fields=['is_active'])
        await database_sync_to_async(self.room.allowed.add)(inactive)
        await database_sync_to_async(self.room.muted_by.add)(inactive)

        await self._run(None, f'@receiver @receiver @sender @{inactive.username} @{outsider.username} @missing')

        self.assertEqual([(group, event['type']) for group, event in self._notifications()], [(f'user_{self.receiver.id}', 'chat.mention')])
        self.push.assert_called_once()
        self.assertEqual(self.push.call_args.args[0], self.receiver)

    async def test_anonymous_sender_hidden_in_ordinary_and_mention_ws_and_fcm(self):
        self.room.public = True
        await database_sync_to_async(self.room.save)(update_fields=['public'])
        for text, kind in (('hello', 'chat.notification'), ('@receiver', 'chat.mention')):
            with self.subTest(kind=kind):
                self.push.reset_mock()
                await self._run(None, text, anonymous=True)
                self.push.assert_called_once()
                [(group, event)] = self._notifications()
                self.assertEqual(group, f'user_{self.receiver.id}')
                self.assertEqual(event['type'], kind)
                self.assertEqual(self.push.call_args.args[0], self.receiver)
                self.assertEqual(self.push.call_args.kwargs['notification_type'], 'chat')
                for payload in (event['notification'], self.push.call_args.args[1]):
                    self.assertIn('Anonymous', payload['body'])
                    self.assertNotIn(self.sender.username, json.dumps(payload))
                    self.assertEqual(payload['room_id'], self.room.id)
                    self.assertIn(f'#room_id={self.room.id}', payload['click_action'])

    async def test_muting_suppresses_ordinary_but_not_explicit_mentions(self):
        await database_sync_to_async(self.room.muted_by.add)(self.receiver)
        await self._run(None)
        self.push.assert_not_called()
        self.assertEqual(self._notifications(), [])

        await self._run(None, '@receiver')
        self.push.assert_called_once()
        self.assertEqual(self.push.call_args.args[0], self.receiver)
        self.assertEqual([(group, event['type']) for group, event in self._notifications()], [(f'user_{self.receiver.id}', 'chat.mention')])

    async def test_present_receiver_skip_is_delegated_to_each_ws_consumer(self):
        await database_sync_to_async(self.room.seen_by.add)(self.receiver)
        receiver = self._make_receiver_consumer()
        receiver.rooms.present.return_value = True
        for text, handler in (('hello', ChatConsumer.chat_notification), ('@receiver', ChatConsumer.chat_mention)):
            with self.subTest(text=text):
                self.push.reset_mock()
                receiver.send_json.reset_mock()
                await self._run(receiver, text)
                self.push.assert_called_once()
                [(group, event)] = self._notifications()
                self.assertEqual(group, f'user_{self.receiver.id}')
                receiver.repo.unsee_room.assert_not_awaited()
                receiver.push_unread_count.assert_not_awaited()
                receiver.send_json.assert_not_awaited()
                receiver.rooms.items.return_value = [self.room.id]
                await handler(receiver, event)
                receiver.send_json.assert_not_awaited()
                receiver.rooms.items.return_value = []
                await handler(receiver, event)
                receiver.send_json.assert_awaited_once_with({'notification': event['notification']})

    async def test_disconnected_consumer_race_still_dispatches_unmuted_notification(self):
        await database_sync_to_async(self.room.seen_by.add)(self.receiver)
        await self._run(None)
        self.push.assert_called_once()
        self.assertEqual(self.push.call_args.args[0], self.receiver)
        self.assertEqual([(group, event['type']) for group, event in self._notifications()], [(f'user_{self.receiver.id}', 'chat.notification')])

    async def test_offline_receiver_read_state_and_cache_invalidated_even_when_muted(self):
        await database_sync_to_async(self.room.seen_by.add)(self.sender, self.receiver)
        await database_sync_to_async(self.room.muted_by.add)(self.receiver)
        sender_key = CHAT_UNREAD_CACHE_KEY.format(user_id=self.sender.id)
        receiver_key = CHAT_UNREAD_CACHE_KEY.format(user_id=self.receiver.id)
        await database_sync_to_async(cache.set_many)({sender_key: 0, receiver_key: 0})

        await self._run(None, online=False)

        self.assertFalse(await database_sync_to_async(self.room.seen_by.filter(pk=self.receiver.pk).exists)())
        self.assertTrue(await database_sync_to_async(self.room.seen_by.filter(pk=self.sender.pk).exists)())
        self.assertIsNone(await database_sync_to_async(cache.get)(receiver_key))
        self.assertEqual(await database_sync_to_async(cache.get)(sender_key), 0)
        self.push.assert_not_called()
        self.assertEqual(self._notifications(), [])


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class MentionNotificationTest(TestCase):
    """Regression tests for _send_mention: room.name crash and room_name value."""

    def setUp(self):
        self.sender = make_user("alice")
        self.receiver = make_user("bob")
        self.room = Room.objects.create(title="alice-bob", public=False)
        self.room.allowed.set([self.sender, self.receiver])

    async def test_send_mention_notification_private_room_uses_sender_username(self):
        """Mention notification for a private room must use the sender's username as room name."""
        message = await database_sync_to_async(lambda: Message.objects.create(room=self.room, sender=self.sender, text="@bob"))()
        channel_layer = AsyncMock()

        with patch('core.notifications.send_fcm_to_user_sync', return_value=1) as push:
            await _send_mention(channel_layer, self.room, message, self.receiver, self.sender.username, None)

        channel_layer.group_send.assert_awaited_once()
        group, payload = channel_layer.group_send.call_args.args
        self.assertEqual(group, f"user_{self.receiver.id}")
        self.assertEqual(payload["type"], "chat.mention")
        self.assertEqual(payload["room_id"], self.room.id)
        self.assertEqual(payload["notification"]["room_id"], self.room.id)
        self.assertIn(f"#room_id={self.room.id}", payload["notification"]["click_action"])

        push.assert_called_once()
        self.assertEqual(push.call_args.args[0], self.receiver)
        self.assertEqual(push.call_args.args[1]['room_name'], self.sender.username)


class BroadcastVoteUpdateTest(TestCase):
    """update_votes w pokojach zadań zawiera nicki głosujących; w innych pokojach nie."""

    def setUp(self):
        self.voter = make_user("voter")
        self.task = make_task(created_by=self.voter)
        self.task_room = self.task.chat_room
        self.plain_room = Room.objects.create(title="plain-room", public=True)

        self.msg_task = Message.objects.create(room=self.task_room, sender=self.voter, text="x")
        self.msg_task.reactions = {'upvotes': [self.voter.id]}
        self.msg_task.save(update_fields=['reactions'])

        self.msg_plain = Message.objects.create(room=self.plain_room, sender=self.voter, text="x")
        self.msg_plain.reactions = {'upvotes': [self.voter.id]}
        self.msg_plain.save(update_fields=['reactions'])

    def _consumer(self):
        consumer = ChatConsumer.__new__(ChatConsumer)
        consumer.scope = {'user': self.voter}
        return consumer

    async def test_task_room_includes_voter_names(self):
        proxy = HandledMessage()
        await self._consumer()._broadcast_vote_update(proxy, self.msg_task.id, 'upvote', 1, 0, True)
        group, message = proxy.get_messages()[0][:2]
        self.assertEqual(group, self.task_room.group_name)
        self.assertEqual(message['update_votes']['upvoters'], ['voter'])
        self.assertEqual(message['update_votes']['downvoters'], [])

    async def test_plain_room_omits_voter_names(self):
        proxy = HandledMessage()
        await self._consumer()._broadcast_vote_update(proxy, self.msg_plain.id, 'upvote', 1, 0, True)
        group, message = proxy.get_messages()[0][:2]
        self.assertEqual(group, self.plain_room.group_name)
        self.assertNotIn('upvoters', message['update_votes'])
        self.assertNotIn('downvoters', message['update_votes'])


class TaskRoomSendPermissionTest(TestCase):
    def setUp(self):
        notification_patch = patch('core.notifications._dispatch_notification')
        notification_patch.start()
        self.addCleanup(notification_patch.stop)
        self.coordinator = make_user("task-coordinator")
        self.helper = make_user("task-helper")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, team_mode=True)
        TaskVote.objects.create(task=self.task, user=self.helper, value=TaskVote.Value.UP)
        self.room = self.task.chat_room
        self.initial_message_count = self.room.messages.count()
        self.assertTrue(self.task.is_user_helper(self.helper))
        self.assertFalse(self.task.is_user_approved(self.helper))

    async def test_send_requires_helper_approval_from_registered_task_policy(self):
        consumer = ChatConsumer.__new__(ChatConsumer)
        consumer.scope = {'user': self.helper}
        consumer.rooms = MagicMock()
        consumer.rooms.items.return_value = [self.room.id]
        consumer.channel_layer = AsyncMock()
        self.assertIsInstance(consumer.repo, ChatRepository)
        proxy = HandledMessage()

        with patch('chat.services._dispatch_message_notifications', new_callable=AsyncMock) as notifications:
            with self.assertRaises(ClientError) as denied:
                await consumer.send_message_to_room(proxy, self.room.id, "Helper message", False, {})

            self.assertEqual(denied.exception.code, "ACCESS_DENIED")
            self.assertEqual(await database_sync_to_async(self.room.messages.count)(), self.initial_message_count)
            consumer.channel_layer.group_send.assert_not_awaited()
            notifications.assert_not_called()
            self.assertEqual(proxy.get_messages(), [])

            await database_sync_to_async(self.task.approve_helper)(self.helper)
            await consumer.send_message_to_room(proxy, self.room.id, "Helper message", False, {})
            await asyncio.sleep(0)

            self.assertEqual(await database_sync_to_async(self.room.messages.count)(), self.initial_message_count + 1)
            saved = await database_sync_to_async(self.room.messages.get)(sender=self.helper, text="Helper message")
            consumer.channel_layer.group_send.assert_awaited_once()
            group, event = consumer.channel_layer.group_send.call_args.args
            self.assertEqual(group, self.room.group_name)
            self.assertEqual(event['type'], 'chat.message')
            self.assertEqual(event['message_id'], saved.pk)
            self.assertEqual(event['room_id'], self.room.pk)
            self.assertEqual(event['user_id'], self.helper.pk)
            notifications.assert_awaited_once()


class HandledMessageSendAllTest(TestCase):
    """Regression tests for HandledMessage.send_all: it must dispatch all queued messages,
    not stop after the first one."""

    async def test_send_all_dispatches_group_consumer_and_self_messages(self):
        """A proxy with a group broadcast, a per-consumer message and a self message must send all three."""
        consumer = MagicMock()
        consumer.channel_layer = AsyncMock()
        consumer.send_json = AsyncMock()

        other_consumer = MagicMock()
        other_consumer.send_json = AsyncMock()

        proxy = HandledMessage()
        proxy.group_send('room_1', {'type': 'chat.message', 'text': 'broadcast'})
        proxy.send_json({'text': 'to_other'}, to_consumer=other_consumer)
        proxy.send_json({'text': 'to_self'})

        await proxy.send_all(consumer)

        consumer.channel_layer.group_send.assert_awaited_once_with('room_1', {'type': 'chat.message', 'text': 'broadcast'})
        other_consumer.send_json.assert_awaited_once_with({'text': 'to_other'})
        consumer.send_json.assert_awaited_once_with({'text': 'to_self'})
