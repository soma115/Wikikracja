import json
import socket
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from chat.federation import (
    _federation_signature,
    _PinnedHTTPSConnection,
    _read_json,
    create_federation_auth_headers,
    decrypt_federation_secret,
    deliver_message,
    encrypt_federation_secret,
    get_federation_inbound_secret,
    get_federation_outbound_secret,
    normalize_instance_url,
    refresh_federated_status,
    validate_outbound_host,
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

    def test_outbound_host_pins_a_public_dns_address(self):
        dns_result = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('93.184.216.34', 443))]

        with patch('chat.federation.socket.getaddrinfo', return_value=dns_result) as resolve:
            pinned_ip = validate_outbound_host('https://remote.test')

        self.assertEqual(pinned_ip, '93.184.216.34')
        resolve.assert_called_once_with('remote.test', 443, type=socket.SOCK_STREAM)

    def test_outbound_host_rejects_mixed_public_and_private_dns_answers(self):
        dns_result = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('93.184.216.34', 443)), (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('127.0.0.1', 443))]

        with patch('chat.federation.socket.getaddrinfo', return_value=dns_result):
            with self.assertRaises(ValueError):
                validate_outbound_host('https://remote.test')

    def test_https_connection_uses_pinned_ip_and_original_host_for_tls(self):
        connection = _PinnedHTTPSConnection('remote.test', 443, '93.184.216.34', timeout=5)
        raw_socket = MagicMock()
        wrapped_socket = MagicMock()
        context = MagicMock()
        context.wrap_socket.return_value = wrapped_socket

        with patch('chat.federation.socket.create_connection', return_value=raw_socket) as create_connection, patch.object(connection, '_context', context):
            connection.connect()

        create_connection.assert_called_once_with(('93.184.216.34', 443), 5, None)
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname='remote.test')
        self.assertIs(connection.sock, wrapped_socket)


@override_settings(DEBUG=True, SITE_DOMAIN='local.test', SITE_NAME='Local group')
class FederationViewsTest(TestCase):
    def setUp(self):
        self.user = make_user('federation-user')
        self.client.force_login(self.user)
        self.secret = 'r' * 32
        self.peer_secret = 's' * 32

    def signed_message_request(self, payload, request_path='/chat/federation/message/'):
        body = json.dumps(payload).encode('utf-8')
        headers = create_federation_auth_headers('POST', request_path, payload['source_url'], body, self.peer_secret.encode('utf-8'))
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
            federation_outbound_secret_ciphertext=encrypt_federation_secret(self.secret),
            federation_inbound_secret_ciphertext=encrypt_federation_secret(self.peer_secret),
        )

    def test_outgoing_json_request_is_signed(self):
        payload = {'source_url': 'http://local.test', 'message': 'Hello'}
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{}'
        response.status = 200

        connection = MagicMock()
        connection.getresponse.return_value = response
        with (
            patch('chat.federation.socket.getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('93.184.216.34', 443))]),
            patch('chat.federation._PinnedHTTPSConnection', return_value=connection) as connection_class,
        ):
            _read_json('https://remote.test/chat/federation/message/', payload, auth_source_url='http://local.test', auth_secret=self.secret.encode('utf-8'))

        connection_class.assert_called_once_with('remote.test', 443, '93.184.216.34', timeout=5)
        method, path = connection.request.call_args.args[:2]
        headers = {name.lower(): value for name, value in connection.request.call_args.kwargs['headers'].items()}
        request_body = connection.request.call_args.kwargs['body']
        expected = _federation_signature(self.secret.encode('utf-8'), method, path, 'http://local.test', headers['x-wikikracja-timestamp'], headers['x-wikikracja-nonce'], request_body)
        self.assertEqual(headers['x-wikikracja-signature'], expected)

    def test_outbound_request_does_not_connect_to_private_dns_answer(self):
        dns_result = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('93.184.216.34', 443)), (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('10.0.0.8', 443))]

        with patch('chat.federation.socket.getaddrinfo', return_value=dns_result), patch('chat.federation._PinnedHTTPSConnection') as connection_class:
            with self.assertRaises(ValueError):
                _read_json('https://remote.test/chat/federation/info/')

        connection_class.assert_not_called()

    def test_outbound_request_does_not_follow_redirects(self):
        dns_result = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('93.184.216.34', 80))]
        response = MagicMock(status=302)
        response.read.return_value = b''
        connection = MagicMock()
        connection.getresponse.return_value = response

        with patch('chat.federation.socket.getaddrinfo', return_value=dns_result), patch('chat.federation._PinnedHTTPConnection', return_value=connection) as connection_class:
            with self.assertRaisesRegex(ValueError, 'HTTP 302'):
                _read_json('http://remote.test/chat/federation/info/')

        connection_class.assert_called_once_with('remote.test', 80, '93.184.216.34', timeout=5)

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
        generated_secret = get_federation_outbound_secret(room.federated_instance_url)
        self.assertEqual(len(generated_secret), 43)
        self.assertIsNone(get_federation_inbound_secret(room.federated_instance_url))
        with patch('chat.federation._read_json', return_value={'accepts_source_url': True}):
            page = self.client.get(reverse('group_settings'))
        self.assertContains(page, generated_secret.decode('utf-8'))
        self.assertNotContains(page, room.federation_outbound_secret_ciphertext)
        self.assertIn('no-store', page.headers['Cache-Control'])

    def test_group_settings_saves_and_rotates_directional_federation_secrets(self):
        room = Room.objects.create(title='Remote group', source_app='federation', public=True, protected=True, federated_instance_url='https://remote.test')
        response = self.client.post(reverse('group_settings'), {'save_federation_inbound_secret': room.federated_instance_url, 'federation_inbound_secret': self.peer_secret})

        self.assertRedirects(response, reverse('group_settings'))
        room.refresh_from_db()
        self.assertTrue(room.has_federation_inbound_secret)
        self.assertFalse(room.has_federation_outbound_secret)
        self.assertNotIn(self.peer_secret, room.federation_inbound_secret_ciphertext)
        self.assertEqual(get_federation_inbound_secret(room.federated_instance_url), self.peer_secret.encode('utf-8'))

        next_peer_secret = 't' * 32
        self.client.post(reverse('group_settings'), {'save_federation_inbound_secret': room.federated_instance_url, 'federation_inbound_secret': next_peer_secret})
        self.assertEqual(get_federation_inbound_secret(room.federated_instance_url), next_peer_secret.encode('utf-8'))
        self.assertIsNone(get_federation_outbound_secret(room.federated_instance_url))

        self.client.post(reverse('group_settings'), {'generate_federation_outbound_secret': room.federated_instance_url})
        own_secret = get_federation_outbound_secret(room.federated_instance_url)
        self.assertEqual(len(own_secret), 43)
        self.assertNotEqual(own_secret, next_peer_secret.encode('utf-8'))
        self.assertEqual(get_federation_inbound_secret(room.federated_instance_url), next_peer_secret.encode('utf-8'))

        with patch('chat.federation._read_json', return_value={'accepts_source_url': True}):
            page = self.client.get(reverse('group_settings'))
        self.assertContains(page, own_secret.decode('utf-8'))
        self.assertContains(page, 'name="federation_inbound_secret"')
        room.refresh_from_db()
        self.assertNotContains(page, room.federation_outbound_secret_ciphertext)

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
        self.create_peer_room()
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': '1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body, headers = self.signed_message_request(payload)

        unsigned_response = self.client.post(reverse('chat:federation_message'), body, content_type='application/json')
        tampered_response = self.client.post(reverse('chat:federation_message'), body + b' ', content_type='application/json', **headers)

        self.assertEqual(unsigned_response.status_code, 401)
        self.assertEqual(tampered_response.status_code, 401)

    def test_message_rejects_signature_for_a_different_source(self):
        self.create_peer_room()
        Room.objects.create(
            title='Other group', source_app='federation', public=True, protected=True, federated_instance_url='https://other.test', federation_inbound_secret_ciphertext=encrypt_federation_secret('o' * 32)
        )
        payload = {'source_url': 'https://other.test', 'source_name': 'Other group', 'source_message_id': '1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body, headers = self.signed_message_request(payload)

        response = self.client.post(reverse('chat:federation_message'), body, content_type='application/json', **headers)

        self.assertEqual(response.status_code, 401)

    def test_message_rejects_signature_for_a_different_path(self):
        self.create_peer_room()
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': 'wrong-path', 'sender_name': 'Remote user', 'message': 'Hello'}
        body, headers = self.signed_message_request(payload, request_path='/chat/federation/other/')

        response = self.client.post(reverse('chat:federation_message'), body, content_type='application/json', **headers)

        self.assertEqual(response.status_code, 401)

    def test_message_rejects_expired_timestamp(self):
        self.create_peer_room()
        payload = {'source_url': 'https://remote.test', 'source_name': 'Remote group', 'source_message_id': 'expired-1', 'sender_name': 'Remote user', 'message': 'Hello'}
        body = json.dumps(payload).encode('utf-8')
        timestamp = '1'
        nonce = 'n' * 24
        signature = _federation_signature(self.peer_secret.encode('utf-8'), 'POST', '/chat/federation/message/', payload['source_url'], timestamp, nonce, body)
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
