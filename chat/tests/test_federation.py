import json
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from chat.federation import (
    _federation_signature,
    _read_json,
    create_federation_auth_headers,
    decrypt_federation_secret,
    deliver_message,
    encrypt_federation_secret,
    get_federation_peer_secret,
    normalize_instance_url,
    refresh_federated_status,
)
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
        self.secret = 'r' * 32

    def signed_message_request(self, payload):
        body = json.dumps(payload).encode('utf-8')
        headers = create_federation_auth_headers('POST', '/chat/federation/message/', payload['source_url'], body, self.secret.encode('utf-8'))
        http_headers = {f'HTTP_{name.upper().replace("-", "_")}': value for name, value in headers.items()}
        return body, http_headers

    def create_peer_room(self):
        return Room.objects.create(
            title='Remote group',
            source_app='federation',
            public=True,
            protected=True,
            federated_instance_url='https://remote.test',
            federated_instance_name='Remote group',
            federation_secret_ciphertext=encrypt_federation_secret(self.secret),
        )

    def test_outgoing_json_request_is_signed(self):
        payload = {'source_url': 'http://local.test', 'message': 'Hello'}
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{}'
        response.status = 200

        with patch('chat.federation._federation_opener.open', return_value=response) as open_request:
            _read_json('https://remote.test/chat/federation/message/', payload, auth_source_url='http://local.test', auth_secret=self.secret.encode('utf-8'))

        request = open_request.call_args.args[0]
        headers = {name.lower(): value for name, value in request.header_items()}
        expected = _federation_signature(self.secret.encode('utf-8'), 'POST', '/chat/federation/message/', 'http://local.test', headers['x-wikikracja-timestamp'], headers['x-wikikracja-nonce'], request.data)
        self.assertEqual(headers['x-wikikracja-signature'], expected)

    def test_info_exposes_only_public_instance_identity(self):
        response = self.client.get(reverse('chat:federation_info'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Local group')
        self.assertEqual(response.json()['url'], 'http://local.test')

    def test_federation_secret_is_encrypted_and_survives_secret_key_rotation(self):
        ciphertext = encrypt_federation_secret(self.secret)

        self.assertNotIn(self.secret, ciphertext)
        with override_settings(SECRET_KEY='rotated-secret-key', SECRET_KEY_FALLBACKS=[settings.SECRET_KEY]):
            self.assertEqual(decrypt_federation_secret(ciphertext), self.secret.encode('utf-8'))

    def test_settings_add_creates_federated_room(self):
        with patch('home.views.discover_instance', return_value='Remote group'):
            response = self.client.post(reverse('group_settings'), {'add_federated_instance': '1', 'federated_instance_url': 'https://remote.test/'})

        self.assertRedirects(response, reverse('group_settings'))
        room = Room.objects.get(federated_instance_url='https://remote.test')
        self.assertEqual(room.title, 'Remote group')
        self.assertEqual(room.source_app, 'federation')
        self.assertIn(self.user, room.allowed.all())
        generated_secret = get_federation_peer_secret(room.federated_instance_url)
        self.assertEqual(len(generated_secret), 43)
        with patch('chat.federation._read_json', return_value={'accepts_source_url': True}):
            page = self.client.get(reverse('group_settings'))
        self.assertContains(page, generated_secret.decode('utf-8'))
        self.assertNotContains(page, room.federation_secret_ciphertext)
        self.assertIn('no-store', page.headers['Cache-Control'])

    def test_group_settings_saves_and_rotates_encrypted_federation_secret(self):
        room = Room.objects.create(title='Remote group', source_app='federation', public=True, protected=True, federated_instance_url='https://remote.test')
        response = self.client.post(reverse('group_settings'), {'save_federated_secret': room.federated_instance_url, 'federated_instance_secret': self.secret})

        self.assertRedirects(response, reverse('group_settings'))
        room.refresh_from_db()
        self.assertTrue(room.has_federation_secret)
        self.assertNotIn(self.secret, room.federation_secret_ciphertext)
        self.assertEqual(get_federation_peer_secret(room.federated_instance_url), self.secret.encode('utf-8'))

        next_secret = 's' * 32
        self.client.post(reverse('group_settings'), {'save_federated_secret': room.federated_instance_url, 'federated_instance_secret': next_secret})
        self.assertEqual(get_federation_peer_secret(room.federated_instance_url), next_secret.encode('utf-8'))

        self.client.post(reverse('group_settings'), {'generate_federated_secret': room.federated_instance_url})
        generated_secret = get_federation_peer_secret(room.federated_instance_url)
        self.assertEqual(len(generated_secret), 43)
        self.assertNotEqual(generated_secret, next_secret.encode('utf-8'))

        with patch('chat.federation._read_json', return_value={'accepts_source_url': True}):
            page = self.client.get(reverse('group_settings'))
        self.assertContains(page, generated_secret.decode('utf-8'))
        self.assertNotContains(page, next_secret)

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
        room = self.create_peer_room()
        room.allowed.add(self.user)
        message = Message.objects.create(room=room, sender=self.user, text='Hello')

        with patch('chat.federation._read_json', return_value={'accepted': True}) as read_json:
            async_to_sync(deliver_message)(room, message)

        payload = read_json.call_args.args[1]
        self.assertEqual(payload['source_url'], 'http://local.test')
        self.assertEqual(payload['source_name'], 'Local group')
        self.assertEqual(payload['message'], 'Hello')
        self.assertEqual(read_json.call_args.kwargs['auth_source_url'], 'http://local.test')
        self.assertEqual(read_json.call_args.kwargs['auth_secret'], self.secret.encode('utf-8'))

    def test_message_requires_a_stored_peer_secret(self):
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': '1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body, headers = self.signed_message_request(payload)

        response = self.client.post(reverse('chat:federation_message'), body, content_type='application/json', **headers)

        self.assertEqual(response.status_code, 401)

    def test_message_rejects_missing_or_tampered_authentication(self):
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': '1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body, headers = self.signed_message_request(payload)

        unsigned_response = self.client.post(reverse('chat:federation_message'), body, content_type='application/json')
        tampered_response = self.client.post(reverse('chat:federation_message'), body + b' ', content_type='application/json', **headers)

        self.assertEqual(unsigned_response.status_code, 401)
        self.assertEqual(tampered_response.status_code, 401)

    def test_message_rejects_expired_timestamp(self):
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': 'expired-1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body = json.dumps(payload).encode('utf-8')
        timestamp = '1'
        nonce = 'n' * 24
        signature = _federation_signature(self.secret.encode('utf-8'), 'POST', '/chat/federation/message/', payload['source_url'], timestamp, nonce, body)
        headers = {'HTTP_X_WIKIKRACJA_TIMESTAMP': timestamp, 'HTTP_X_WIKIKRACJA_NONCE': nonce, 'HTTP_X_WIKIKRACJA_SIGNATURE': signature}

        response = self.client.post(reverse('chat:federation_message'), body, content_type='application/json', **headers)

        self.assertEqual(response.status_code, 401)

    def test_message_is_accepted_for_configured_peer(self):
        room = self.create_peer_room()
        room.allowed.add(self.user)
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': '1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body, headers = self.signed_message_request(payload)

        with patch('chat.views.send_message', new=AsyncMock()) as send_message:
            response = self.client.post(reverse('chat:federation_message'), body, content_type='application/json', **headers)

        self.assertEqual(response.status_code, 200)
        send_message.assert_awaited_once()
        self.assertEqual(send_message.await_args.kwargs['propagate_federated'], False)
        self.assertEqual(send_message.await_args.kwargs['sender_display_name'], 'Remote user')
        self.assertEqual(send_message.await_args.kwargs['federation_source_url'], 'https://remote.test')
        self.assertEqual(send_message.await_args.args[0], room)

    def test_message_rejects_replayed_nonce(self):
        self.create_peer_room()
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': 'replay-1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body, headers = self.signed_message_request(payload)

        with patch('chat.views.send_message', new=AsyncMock()) as send_message:
            accepted = self.client.post(reverse('chat:federation_message'), body, content_type='application/json', **headers)
            replayed = self.client.post(reverse('chat:federation_message'), body, content_type='application/json', **headers)

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(replayed.status_code, 401)
        send_message.assert_awaited_once()
