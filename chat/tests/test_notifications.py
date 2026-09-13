import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from chat.management.commands.run_chat_notifications_worker import Command
from chat.notification_queue import STREAM_NAME, enqueue_notification, read_notifications
from chat.tests.utils import make_user


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

    def test_read_notifications_decodes_stream_fields(self):
        client = MagicMock()
        client.xreadgroup.return_value = [(STREAM_NAME, [('1-0', {'job_id': 'job-1', 'user_id': '7', 'room_id': '11', 'kind': 'notification', 'notification': '{"body":"Hello"}'})])]

        result = read_notifications(client, 'worker-1', count=3, block_ms=100)

        self.assertEqual(result, [('1-0', {'job_id': 'job-1', 'user_id': 7, 'room_id': 11, 'kind': 'notification', 'notification': {'body': 'Hello'}})])
        client.xreadgroup.assert_called_once()


class NotificationWorkerTest(TestCase):
    def test_failed_job_remains_pending_for_retry(self):
        client = MagicMock()
        client.exists.return_value = False
        job = {'job_id': 'job-failed', 'user_id': 1, 'room_id': 11, 'kind': 'notification', 'notification': {'notification_id': 'notification-failed'}}

        with patch('chat.management.commands.run_chat_notifications_worker.deliver_notification_job', side_effect=RuntimeError('temporary delivery failure')):
            Command._process_job(client, '1-0', job)

        client.xack.assert_not_called()
        client.set.assert_not_called()

    def test_completed_job_is_delivered_once(self):
        user = make_user('notification-worker-user')
        client = MagicMock()
        client.exists.side_effect = [False, True]
        job = {'job_id': 'job-once', 'user_id': user.id, 'room_id': 11, 'kind': 'notification', 'notification': {'notification_id': 'notification-1'}}

        with patch('chat.management.commands.run_chat_notifications_worker.deliver_notification_job') as deliver:
            Command._process_job(client, '1-0', job)
            Command._process_job(client, '1-1', job)

        deliver.assert_called_once_with(job)
        client.set.assert_called_once_with('wikikracja:chat:notification-delivered:job-once', '1', ex=7 * 24 * 60 * 60)
        self.assertEqual(client.xack.call_count, 2)
