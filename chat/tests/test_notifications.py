import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from chat.management.commands.run_chat_notifications_worker import Command
from chat.notification_queue import (
    CHAT_PUSH_COOLDOWN_SECONDS,
    CHAT_PUSH_DELAYED_KEY,
    STREAM_NAME,
    clear_room_notification_state,
    deliver_due_chat_notifications,
    dispatch_or_defer_chat_notification,
    enqueue_notification,
    read_notifications,
)
from chat.tests.utils import make_user


class MemoryLock:
    def __init__(self, client, key):
        self.client = client
        self.key = key

    def acquire(self, blocking=False, blocking_timeout=None):
        if self.key in self.client.locks:
            return False
        self.client.locks.add(self.key)
        return True

    def release(self):
        self.client.locks.discard(self.key)


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.sorted_sets = {}
        self.locks = set()

    def lock(self, key, timeout):
        return MemoryLock(self, key)

    def get(self, key):
        return self.values.get(key)

    def exists(self, key):
        return key in self.values

    def set(self, key, value, ex=None):
        self.values[key] = value

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)

    def zadd(self, name, mapping):
        self.sorted_sets.setdefault(name, {}).update(mapping)

    def zrem(self, name, member):
        self.sorted_sets.setdefault(name, {}).pop(member, None)

    def zrangebyscore(self, name, minimum, maximum, start=0, num=None):
        values = self.sorted_sets.get(name, {})
        matches = [member for member, score in sorted(values.items(), key=lambda item: item[1]) if score <= float(maximum)]
        return matches[start:] if num is None else matches[start : start + num]


class ChatNotificationThrottleTest(TestCase):
    def test_notifications_coalesce_to_latest_per_user_and_room(self):
        client = MemoryRedis()
        delivered = []

        def make_job(user_id, room_id, job_id):
            return {'user_id': user_id, 'room_id': room_id, 'job_id': job_id, 'kind': 'notification', 'notification': {'body': job_id}}

        self.assertTrue(dispatch_or_defer_chat_notification(client, make_job(1, 10, 'first'), delivered.append, now=1000))
        self.assertTrue(dispatch_or_defer_chat_notification(client, make_job(1, 10, 'second'), delivered.append, now=1100))
        self.assertTrue(dispatch_or_defer_chat_notification(client, make_job(1, 10, 'latest'), delivered.append, now=2000))
        self.assertTrue(dispatch_or_defer_chat_notification(client, make_job(1, 11, 'other-room'), delivered.append, now=2000))

        self.assertEqual([job['job_id'] for job in delivered], ['first', 'other-room'])
        self.assertEqual(deliver_due_chat_notifications(client, delivered.append, now=1000 + CHAT_PUSH_COOLDOWN_SECONDS - 1), 0)
        self.assertEqual(deliver_due_chat_notifications(client, delivered.append, now=1000 + CHAT_PUSH_COOLDOWN_SECONDS), 1)
        self.assertEqual([job['job_id'] for job in delivered], ['first', 'other-room', 'latest'])

    def test_opening_room_clears_cooldown_and_pending_notification(self):
        client = MemoryRedis()
        delivered = []
        first = {'user_id': 2, 'room_id': 20, 'job_id': 'first', 'kind': 'notification', 'notification': {'body': 'first'}}
        pending = {'user_id': 2, 'room_id': 20, 'job_id': 'pending', 'kind': 'notification', 'notification': {'body': 'pending'}}

        dispatch_or_defer_chat_notification(client, first, delivered.append, now=1000)
        dispatch_or_defer_chat_notification(client, pending, delivered.append, now=1100)
        self.assertTrue(clear_room_notification_state(2, 20, client=client))
        next_job = {**pending, 'job_id': 'after-open'}
        dispatch_or_defer_chat_notification(client, next_job, delivered.append, now=1200)

        self.assertEqual([job['job_id'] for job in delivered], ['first', 'after-open'])
        self.assertEqual(client.sorted_sets.get(CHAT_PUSH_DELAYED_KEY, {}), {})


class NotificationQueueTest(TestCase):
    def test_enqueue_creates_consumer_group_and_serializes_job(self):
        client = MagicMock()
        with patch('chat.notification_queue._redis_client', return_value=client):
            job_id = enqueue_notification(user_id=7, room_id=11, notification={'notification_id': 'notification-1', 'body': 'Hello'}, kind='mention')

        self.assertEqual(job_id, 'message:notification-1:7:mention')
        client.xgroup_create.assert_called_once_with(STREAM_NAME, 'chat-notification-workers', id='0', mkstream=True)
        args, kwargs = client.xadd.call_args
        self.assertEqual(args[0], STREAM_NAME)
        self.assertEqual(args[1]['job_id'], job_id)
        self.assertEqual(json.loads(args[1]['notification'])['body'], 'Hello')
        self.assertEqual(kwargs['maxlen'], 10_000)
        self.assertTrue(kwargs['approximate'])

    def test_enqueue_preserves_an_event_specific_push_key(self):
        client = MagicMock()
        with patch('chat.notification_queue._redis_client', return_value=client):
            enqueue_notification(user_id=7, room_id=11, notification={'notification_id': 'notification-2'}, kind='notification', push_event='vote.argument_added')

        self.assertEqual(client.xadd.call_args.args[1]['push_event'], 'vote.argument_added')

    def test_read_notifications_decodes_stream_fields(self):
        client = MagicMock()
        client.xreadgroup.return_value = [
            (STREAM_NAME, [('1-0', {'job_id': 'job-1', 'user_id': '7', 'room_id': '11', 'kind': 'notification', 'push_event': 'vote.argument_added', 'notification': '{"body":"Hello"}'})])
        ]

        result = read_notifications(client, 'worker-1', count=3, block_ms=100)

        self.assertEqual(result, [('1-0', {'job_id': 'job-1', 'user_id': 7, 'room_id': 11, 'kind': 'notification', 'push_event': 'vote.argument_added', 'notification': {'body': 'Hello'}})])
        client.xreadgroup.assert_called_once()


class ChatNotificationDeliveryTest(TestCase):
    def test_worker_routes_message_and_mention_to_distinct_event_keys(self):
        from chat.notifications import deliver_notification_job

        user = make_user('chat-push-event-user')
        cases = (('notification', 'chat.message', 'chat'), ('mention', 'chat.mention', 'chat'), ('notification', 'vote.argument_added', 'glosowania'))
        for index, (kind, event_key, notification_type) in enumerate(cases):
            notification = {'notification_id': f'notification-{index}', 'room_id': 11, 'source_user_id': None}
            job = {'job_id': f'job-{index}', 'user_id': user.pk, 'room_id': 11, 'kind': kind, 'notification': notification, 'push_event': event_key}
            with (
                self.subTest(kind=kind, event_key=event_key),
                patch('chat.notifications.core_notifications.send_websocket_to_user_sync') as websocket,
                patch('chat.notifications.core_notifications.send_fcm_to_user_sync') as fcm,
            ):
                deliver_notification_job(job)

            ws_type = 'chat.mention' if kind == 'mention' else 'chat.notification'
            websocket.assert_called_once_with(user.id, {**notification, 'room_id': 11}, ws_type=ws_type, notification_type=notification_type, push_event=event_key)
            fcm.assert_called_once_with(user, {**notification, 'room_id': 11}, notification_type=notification_type, source_user_id=None, push_event=event_key)


class NotificationWorkerTest(TestCase):
    def test_failed_job_remains_pending_for_retry(self):
        client = MagicMock()
        client.exists.return_value = False
        client.get.return_value = None
        job = {'job_id': 'job-failed', 'user_id': 1, 'room_id': 11, 'kind': 'notification', 'notification': {'notification_id': 'notification-failed'}}

        with patch('chat.management.commands.run_chat_notifications_worker.deliver_notification_job', side_effect=RuntimeError('temporary delivery failure')):
            Command._process_job(client, '1-0', job)

        client.xack.assert_not_called()
        client.set.assert_not_called()

    def test_completed_job_is_delivered_once(self):
        user = make_user('notification-worker-user')
        client = MagicMock()
        client.exists.side_effect = [False, False, True]
        client.get.return_value = None
        job = {'job_id': 'job-once', 'user_id': user.id, 'room_id': 11, 'kind': 'notification', 'notification': {'notification_id': 'notification-1'}}

        with patch('chat.management.commands.run_chat_notifications_worker.deliver_notification_job') as deliver:
            Command._process_job(client, '1-0', job)
            Command._process_job(client, '1-1', job)

        deliver.assert_called_once_with(job)
        client.set.assert_any_call('wikikracja:chat:notification-delivered:job-once', '1', ex=7 * 24 * 60 * 60)
        self.assertEqual(client.xack.call_count, 2)

    def test_deferred_job_is_acknowledged_without_marking_it_delivered(self):
        client = MagicMock()
        client.exists.side_effect = [False, False]
        client.get.return_value = '9999999999'
        job = {'job_id': 'job-deferred', 'user_id': 1, 'room_id': 11, 'kind': 'notification', 'notification': {'notification_id': 'notification-deferred'}}

        with patch('chat.management.commands.run_chat_notifications_worker.deliver_notification_job') as deliver:
            Command._process_job(client, '1-0', job)

        deliver.assert_not_called()
        client.set.assert_any_call('wikikracja:chat:notification-deferred:job-deferred', '1', ex=7 * 24 * 60 * 60)
        assert all(call.args[0] != 'wikikracja:chat:notification-delivered:job-deferred' for call in client.set.call_args_list)
        client.xack.assert_called_once_with('wikikracja:chat:notifications', 'chat-notification-workers', '1-0')
