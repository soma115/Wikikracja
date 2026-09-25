from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import TestCase, override_settings
from django.urls import reverse

from chat.federation import deliver_message, normalize_instance_url, refresh_federated_status
from chat.models import Message, Room
from chat.tests.utils import make_user


class FederationUrlTest(TestCase):
    @override_settings(DEBUG=True)
    def test_normalizes_only_instance_origin(self):
        self.assertEqual(normalize_instance_url('http://example.test/'), 'http://example.test')
        self.assertEqual(normalize_instance_url('https://example.test'), 'https://example.test')

    @override_settings(DEBUG=True)
    def test_rejects_paths_and_credentials(self):
        for value in ('https://example.test/chat/', 'https://user:pass@example.test/'):
            with self.assertRaises(ValueError):
                normalize_instance_url(value)


@override_settings(DEBUG=True, SITE_DOMAIN='local.test', SITE_NAME='Local group')
class FederationViewsTest(TestCase):
    def setUp(self):
        self.user = make_user('federation-user')
        self.client.force_login(self.user)

    def test_info_exposes_only_public_instance_identity(self):
        response = self.client.get(reverse('chat:federation_info'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Local group')
        self.assertEqual(response.json()['url'], 'http://local.test')

    def test_settings_add_creates_federated_room(self):
        with patch('home.views.discover_instance', return_value='Remote group'):
            response = self.client.post(reverse('group_settings'), {'add_federated_instance': '1', 'federated_instance_url': 'https://remote.test/'})

        self.assertRedirects(response, reverse('group_settings'))
        room = Room.objects.get(federated_instance_url='https://remote.test')
        self.assertEqual(room.title, 'Remote group')
        self.assertEqual(room.source_app, 'federation')
        self.assertIn(self.user, room.allowed.all())

    def test_status_reports_peer_configuration_and_communication(self):
        room = Room.objects.create(title='Remote group', source_app='federation', public=True, protected=True, federated_instance_url='https://remote.test', federated_instance_name='Remote group')
        with patch('chat.federation._read_json', return_value={'accepts_source_url': True}):
            refresh_federated_status(room, force=True)

        room.refresh_from_db()
        self.assertTrue(room.federation_peer_configured)
        self.assertTrue(room.federation_communication_ok)
        self.assertIsNotNone(room.federation_last_checked_at)
        self.assertIsNotNone(room.federation_last_communication_at)

    def test_delivery_reads_site_name_without_sync_database_error(self):
        room = Room.objects.create(title='Remote group', source_app='federation', public=True, protected=True, federated_instance_url='https://remote.test', federated_instance_name='Remote group')
        room.allowed.add(self.user)
        message = Message.objects.create(room=room, sender=self.user, text='Hello')

        with patch('chat.federation._read_json', return_value={'accepted': True}) as read_json:
            async_to_sync(deliver_message)(room, message)

        payload = read_json.call_args.args[1]
        self.assertEqual(payload['source_url'], 'http://local.test')
        self.assertEqual(payload['source_name'], 'Local group')
        self.assertEqual(payload['message'], 'Hello')

    def test_message_requires_mutual_configuration(self):
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': '1', 'sender_name': 'Remote user', 'message': 'Hello'}

        response = self.client.post(reverse('chat:federation_message'), payload, content_type='application/json')

        self.assertEqual(response.status_code, 403)

    def test_message_is_accepted_for_configured_peer(self):
        room = Room.objects.create(title='Remote group', source_app='federation', public=True, protected=True, federated_instance_url='https://remote.test', federated_instance_name='Remote group')
        room.allowed.add(self.user)
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': '1', 'sender_name': 'Remote user', 'message': 'Hello'}

        with patch('chat.views.send_message', new=AsyncMock()) as send_message:
            response = self.client.post(reverse('chat:federation_message'), payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        send_message.assert_awaited_once()
        self.assertEqual(send_message.await_args.kwargs['propagate_federated'], False)
        self.assertEqual(send_message.await_args.kwargs['sender_display_name'], 'Remote user')
        self.assertEqual(send_message.await_args.kwargs['federation_source_url'], 'https://remote.test')
        self.assertEqual(send_message.await_args.args[0], room)
