import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from django.db import DatabaseError
from push_notifications.models import GCMDevice

from core import notifications as notify

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def transport(monkeypatch):
    channel = SimpleNamespace(group_send=AsyncMock())
    thread, mail = Mock(), Mock()
    monkeypatch.setattr(notify, '_fcm_ready', lambda: True)
    monkeypatch.setattr(notify, '_gcm_migrated', True)
    monkeypatch.setattr(notify, '_icon_url', lambda: '/static/test-icon.ico')
    monkeypatch.setattr(notify, 'get_channel_layer', lambda: channel)
    monkeypatch.setattr(notify, 'threading', SimpleNamespace(Thread=thread))
    monkeypatch.setattr(notify, 'send_mail', mail)
    with patch.object(type(GCMDevice.objects.all()), 'send_message', autospec=True) as fcm:
        fcm.side_effect = lambda qs, message: SimpleNamespace(success_count=qs.count(), responses=[])
        yield SimpleNamespace(fcm=fcm, channel=channel, thread=thread, mail=mail)


@pytest.fixture
def users(django_user_model):
    def create(name, active=True, **preferences):
        user = django_user_model.objects.create_user(username=name, is_active=active)
        for field, value in preferences.items():
            setattr(user.uzytkownik, field, value)
        user.uzytkownik.save()
        return user

    return create


@pytest.fixture
def payload():
    return notify.build_notification('Title', 'Body', '/vote/7', 'vote-7', vote_id=7)


def device(user, name='desktop', **kwargs):
    return GCMDevice.objects.create(user=user, name=name, registration_id=f'local-test-{user.pk}-{GCMDevice.objects.count()}', **{'active': True, 'cloud_message_type': 'FCM', **kwargs})


@pytest.mark.parametrize('category', ['obywatele', 'glosowania', 'chat', 'events', 'post', 'task', 'survey'])
def test_category_selects_only_active_opted_in_users(users, payload, transport, category, django_assert_num_queries):
    field = f'push_notifications_{category}'
    enabled = users('enabled', **dict.fromkeys(notify._PUSH_FIELDS.values(), False))
    setattr(enabled.uzytkownik, field, True)
    enabled.uzytkownik.save()
    disabled = users('disabled', **{field: False})
    inactive = users('inactive', active=False)
    for user in (enabled, disabled, inactive):
        device(user)
    assert notify._push_user_ids(category) == {enabled.pk}
    assert notify._push_enabled_for_user(enabled, category) is True
    with django_assert_num_queries(0):
        assert notify.send_fcm_to_user_sync(disabled, payload, category) == 0
    transport.fcm.assert_not_called()
    assert notify.send_fcm_to_all_sync(payload, notification_type=category) == 1
    assert set(transport.fcm.call_args.args[0].values_list('user_id', flat=True)) == {enabled.pk}


@pytest.mark.parametrize('scope', ['user', 'broadcast', 'subset'])
@pytest.mark.parametrize('phone,computer', [(True, True), (False, True), (True, False), (False, False)])
def test_device_selection_respects_owner_activity_fcm_and_type(users, payload, transport, scope, phone, computer):
    user = users('target', push_phone_enabled=phone, push_computer_enabled=computer)
    expected = set()
    for name, allowed in [('mobile', phone), ('tablet', phone), ('desktop', computer)]:
        registered = device(user, name)
        if allowed:
            expected.add(registered.pk)
    device(user, active=False)
    device(user, cloud_message_type='GCM')
    device(users('other', active=scope != 'broadcast'))
    if scope == 'user':
        count = notify.send_fcm_to_user_sync(user, payload)
    else:
        count = notify.send_fcm_to_all_sync(payload, user_ids=[user.pk] if scope == 'subset' else None)
    assert count == len(expected)
    if expected:
        transport.fcm.assert_called_once()
        assert set(transport.fcm.call_args.args[0].values_list('pk', flat=True)) == expected
    else:
        transport.fcm.assert_not_called()


@pytest.mark.parametrize('scope', ['broadcast', 'subset'])
def test_broadcast_device_preferences_are_per_owner_without_extra_queries(users, payload, transport, scope, django_assert_num_queries):
    phone = users('phone', push_computer_enabled=False)
    computer = users('computer', push_phone_enabled=False)
    disabled = users('disabled', push_phone_enabled=False, push_computer_enabled=False)
    missing = users('missing')
    missing.uzytkownik.delete()
    expected = set()
    for user in (phone, computer, disabled, missing):
        for name in ('mobile', 'tablet', 'desktop', 'unknown', '', None):
            registered = device(user, name)
            if user == missing or name in ('unknown', '', None) or (user == phone and name != 'desktop') or (user == computer and name == 'desktop'):
                expected.add(registered.pk)
    user_ids = [user.pk for user in (phone, computer, disabled, missing)] if scope == 'subset' else None
    with django_assert_num_queries(2):
        assert notify.send_fcm_to_all_sync(payload, user_ids=user_ids) == len(expected)
    transport.fcm.assert_called_once()
    assert set(transport.fcm.call_args.args[0].values_list('pk', flat=True)) == expected


def test_explicit_push_recipients_bypass_category_lookup_but_not_device_optouts(users, payload, transport):
    user = users('target', push_notifications_events=False, push_phone_enabled=False)
    expected = device(user, 'desktop')
    device(user, 'mobile')
    device(user, 'tablet')
    with patch.object(notify, '_push_user_ids') as recipients:
        assert notify.send_fcm_to_all_sync(payload, user_ids=[user.pk], notification_type='events') == 1
    recipients.assert_not_called()
    assert set(transport.fcm.call_args.args[0].values_list('pk', flat=True)) == {expected.pk}


@pytest.mark.parametrize('selection', ['all', 'subset', 'empty'])
def test_broadcast_optional_recipients(users, payload, transport, selection, django_assert_num_queries):
    first, second, inactive = users('first'), users('second'), users('inactive', active=False)
    expected = {device(first).pk, device(second).pk}
    device(inactive)
    kwargs = {}
    if selection == 'subset':
        kwargs['user_ids'] = [first.pk, inactive.pk]
        expected = {GCMDevice.objects.get(user=first).pk}
    elif selection == 'empty':
        kwargs['user_ids'], expected = [], set()
    if expected:
        assert notify.send_fcm_to_all_sync(payload, **kwargs) == len(expected)
        assert set(transport.fcm.call_args.args[0].values_list('pk', flat=True)) == expected
    else:
        with django_assert_num_queries(0):
            assert notify.send_fcm_to_all_sync(payload, **kwargs) == 0
        transport.fcm.assert_not_called()


def test_broadcast_reuses_category_recipients_for_both_channels(users, payload):
    enabled = users('enabled')
    users('disabled', push_notifications_events=False)
    with patch.object(notify, '_push_user_ids', wraps=notify._push_user_ids) as recipients:
        with patch.object(notify, 'send_fcm_to_all_sync') as fcm, patch.object(notify, 'send_websocket_to_all_sync') as ws:
            notify.send_notification_to_all_sync(payload, ws_type='event.notification', notification_type='events')
    recipients.assert_called_once_with('events')
    fcm.assert_called_once_with(payload, user_ids={enabled.pk})
    ws.assert_called_once_with(payload, 'event.notification', user_ids={enabled.pk})


def test_legacy_gcm_device_is_converted_before_first_send(users, payload, monkeypatch):
    legacy = device(users('legacy'), cloud_message_type='GCM')
    monkeypatch.setattr(notify, '_gcm_migrated', False)
    assert notify.send_fcm_to_user_sync(legacy.user, payload) == 1
    legacy.refresh_from_db()
    assert legacy.cloud_message_type == 'FCM'
    assert notify._gcm_migrated is True


@pytest.mark.parametrize('category', [None, '', 'unknown-category'])
def test_unspecified_categories_do_not_query_preferences(category, django_assert_num_queries):
    with django_assert_num_queries(0):
        assert notify._push_user_ids(category) is None
        assert notify._push_enabled_for_user(SimpleNamespace(), category) is True


@pytest.mark.parametrize('selection', ['category', 'subset', 'empty', 'all'])
def test_websocket_recipient_groups_and_preferences(users, payload, transport, selection):
    first = users('first')
    second = users('second', push_notifications_events=False)
    inactive = users('inactive', active=False)
    kwargs, expected = {}, {first.pk, second.pk}
    if selection == 'category':
        kwargs, expected = {'notification_type': 'events'}, {first.pk}
    elif selection == 'subset':
        kwargs, expected = {'user_ids': [second.pk, inactive.pk]}, {second.pk}
    elif selection == 'empty':
        kwargs, expected = {'user_ids': []}, set()
    notify.send_websocket_to_all_sync(payload, ws_type='event.notification', **kwargs)
    calls = transport.channel.group_send.await_args_list
    assert {call.args[0] for call in calls} == {f'user_{pk}' for pk in expected}
    assert len(calls) == len(expected)
    assert all(call.args[1] == {'type': 'event.notification', 'notification': payload} for call in calls)


def test_websocket_failure_does_not_skip_remaining_recipients(users, payload, transport):
    first, second = users('first'), users('second')
    transport.channel.group_send.side_effect = [RuntimeError('local channel failure'), None]
    notify.send_websocket_to_all_sync(payload)
    assert {call.args[0] for call in transport.channel.group_send.await_args_list} == {f'user_{first.pk}', f'user_{second.pk}'}
    transport.channel.group_send.reset_mock(side_effect=True)
    transport.channel.group_send.side_effect = RuntimeError('local channel failure')
    assert notify.send_websocket_to_user_sync(first.pk, payload, 'vote.notification') is None
    transport.channel.group_send.assert_awaited_once_with(f'user_{first.pk}', {'type': 'vote.notification', 'notification': payload})


def test_missing_channel_layer_skips_queries(payload, monkeypatch, django_assert_num_queries):
    monkeypatch.setattr(notify, 'get_channel_layer', lambda: None)
    with django_assert_num_queries(0):
        assert notify.send_websocket_to_all_sync(payload, notification_type='events') is None
        assert notify.send_websocket_to_user_sync(1, payload) is None


def test_recipient_database_failure_fails_closed(payload, transport, django_user_model):
    with patch.object(django_user_model.objects, 'filter', side_effect=DatabaseError('local database failure')):
        assert notify._push_user_ids('events') == set()
        notify.send_notification_to_all_sync(payload, notification_type='events')
    transport.fcm.assert_not_called()
    transport.channel.group_send.assert_not_awaited()


@pytest.mark.parametrize('broadcast', [False, True], ids=['user', 'broadcast'])
@pytest.mark.parametrize('outcome', ['none', 'partial', 'runtime-error', 'database-error'])
def test_fcm_backend_outcomes_do_not_trigger_other_channels(users, payload, transport, broadcast, outcome):
    user = users('target')
    device(user, 'mobile')
    device(user, 'desktop')
    transport.fcm.side_effect = None
    transport.fcm.return_value = None
    if outcome == 'partial':
        transport.fcm.return_value = SimpleNamespace(success_count=1, responses=[SimpleNamespace(success=True), SimpleNamespace(success=False, exception=RuntimeError('local rejection'))])
    elif outcome.endswith('error'):
        transport.fcm.side_effect = (DatabaseError if outcome == 'database-error' else RuntimeError)('local transport failure')
    count = notify.send_fcm_to_all_sync(payload) if broadcast else notify.send_fcm_to_user_sync(user, payload)
    assert count == (1 if outcome == 'partial' else 0)
    transport.fcm.assert_called_once()
    transport.channel.group_send.assert_not_awaited()
    transport.mail.assert_not_called()


@pytest.mark.parametrize('push,websocket', [(True, False), (False, True), (False, False), (True, True)])
def test_dispatch_honors_independent_channel_flags(push, websocket, transport):
    with patch.object(notify, 'send_fcm_to_all_sync') as fcm, patch.object(notify, 'send_websocket_to_all_sync') as ws:
        notify._dispatch_notification('Title', 'Body', '/vote/7', 'vote-7', send_push=push, send_websocket=websocket, send_email=False, in_thread=False)
    assert fcm.call_count == int(push)
    assert ws.call_count == int(websocket)
    transport.mail.assert_not_called()
    transport.thread.assert_not_called()


@pytest.mark.parametrize('entrypoint', ['sync', 'thread', 'dispatch-background'])
@pytest.mark.parametrize('push,websocket', [(True, False), (False, True), (False, False), (True, True)])
def test_channel_flags_reach_transports_and_skip_unused_recipient_queries(users, payload, transport, entrypoint, push, websocket, django_assert_num_queries):
    user = users('target')
    device(user)
    options = {'send_push': push, 'send_websocket': websocket, 'notification_type': 'events', 'ws_type': 'event.notification'}
    with patch.object(notify, '_push_user_ids', wraps=notify._push_user_ids) as recipients:
        with django_assert_num_queries(1 + 2 * int(push) + int(websocket) if push or websocket else 0):
            if entrypoint == 'sync':
                notify.send_notification_to_all_sync(payload, **options)
            elif entrypoint == 'thread':
                notify.send_notification_to_all_in_thread(payload, **options)
            else:
                notify._dispatch_notification('Title', 'Body', '/vote/7', 'vote-7', in_thread=True, send_email=False, **options)
            if transport.thread.called:
                thread_options = transport.thread.call_args.kwargs
                thread_options['target'](*thread_options['args'], **thread_options['kwargs'])
    if push or websocket:
        recipients.assert_called_once_with('events')
    else:
        recipients.assert_not_called()
    assert transport.fcm.call_count == int(push)
    assert transport.channel.group_send.await_count == int(websocket)
    if push:
        assert set(transport.fcm.call_args.args[0].values_list('user_id', flat=True)) == {user.pk}
    if websocket:
        assert transport.channel.group_send.await_args.args[0] == f'user_{user.pk}'
    transport.mail.assert_not_called()


@pytest.mark.parametrize('background', [False, True])
@pytest.mark.parametrize('daemon', [False, True])
def test_dispatch_forwards_execution_options_without_leaking_them(background, daemon):
    with patch.object(notify, 'send_notification_to_all_sync') as sync, patch.object(notify, 'send_notification_to_all_in_thread') as threaded:
        notify._dispatch_notification('Title', 'Body', '/vote/7', 'vote-7', in_thread=background, daemon=daemon, notification_type='glosowania', ws_type='vote.notification', send_email=False, vote_id=7)
    selected, unused = (threaded, sync) if background else (sync, threaded)
    selected.assert_called_once()
    unused.assert_not_called()
    payload = selected.call_args.args[0]
    expected = {'ws_type': 'vote.notification', 'notification_type': 'glosowania', 'send_push': True, 'send_websocket': True}
    if background:
        expected['daemon'] = daemon
    assert selected.call_args.kwargs == expected
    assert set(payload) == {'notification_id', 'title', 'body', 'icon', 'click_action', 'tag', 'vote_id'}
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize('daemon', [None, False, True])
def test_background_wrapper_constructs_thread_without_running_target(payload, transport, daemon):
    options = {} if daemon is None else {'daemon': daemon}
    thread = notify.send_notification_to_all_in_thread(payload, ws_type='vote.notification', notification_type='glosowania', **options)
    transport.thread.assert_called_once_with(
        target=notify.send_notification_to_all_sync,
        args=(payload,),
        kwargs={'ws_type': 'vote.notification', 'notification_type': 'glosowania', 'send_push': True, 'send_websocket': True},
        daemon=True if daemon is None else daemon,
    )
    assert thread is transport.thread.return_value
    thread.start.assert_called_once_with()
    transport.fcm.assert_not_called()
    transport.channel.group_send.assert_not_awaited()


@pytest.mark.parametrize(
    'overrides,expected',
    [
        ({}, ('Title', 'Body')),
        ({'email_subject': 'Email title', 'email_body': 'Email body'}, ('Email title', 'Email body')),
        ({'email_body': 'Fallback', 'recipient_subject': 'Recipient', 'recipient_body': 'Private'}, ('Recipient', 'Private')),
    ],
)
def test_email_only_dispatch_overrides_and_recipient(overrides, expected, transport, settings):
    notify._dispatch_notification('Title', 'Body', '/vote/7', 'vote-7', send_push=False, send_websocket=False, recipient_email='recipient@example.test', **overrides)
    transport.mail.assert_called_once_with(*expected, settings.DEFAULT_FROM_EMAIL, ['recipient@example.test'], fail_silently=False)
    transport.thread.assert_not_called()
    transport.fcm.assert_not_called()
    transport.channel.group_send.assert_not_awaited()


@pytest.mark.parametrize('send_email,recipient', [(False, 'recipient@example.test'), (True, None)])
def test_email_requires_enabled_channel_and_explicit_recipient(transport, send_email, recipient):
    notify._dispatch_notification('Title', 'Body', '/', 'email', send_push=False, send_websocket=False, send_email=send_email, recipient_email=recipient)
    transport.mail.assert_not_called()
    transport.thread.assert_not_called()


@pytest.mark.parametrize('raise_on_error', [False, True])
def test_email_backend_failure_respects_raise_on_error(transport, raise_on_error):
    transport.mail.side_effect = RuntimeError('local email failure')
    options = {'send_push': False, 'send_websocket': False, 'recipient_email': 'recipient@example.test', 'raise_on_error': raise_on_error}
    if raise_on_error:
        with pytest.raises(RuntimeError, match='local email failure'):
            notify._dispatch_notification('Title', 'Body', '/', 'email', **options)
    else:
        assert notify._dispatch_notification('Title', 'Body', '/', 'email', **options) is None
    transport.mail.assert_called_once()
    transport.fcm.assert_not_called()
    transport.channel.group_send.assert_not_awaited()


def test_fcm_payload_stringifies_metadata_without_adding_identity(payload):
    original = payload.copy()
    message = notify._build_fcm_message(payload)
    assert message.data == {key: str(value) for key, value in original.items()}
    assert message.webpush.notification.data == {'click_action': '/vote/7', 'vote_id': '7'}
    assert payload == original
    assert set(message.data) == {'notification_id', 'title', 'body', 'icon', 'click_action', 'tag', 'vote_id'}
