from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from push_notifications.models import GCMDevice

from core import notifications as notify
from core.services.notifications import make_unsubscribe_token, unsubscribe_user_notifications

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def transport(monkeypatch):
    channel = SimpleNamespace(group_send=AsyncMock())
    mail = Mock()
    monkeypatch.setattr(notify, '_fcm_ready', lambda: True)
    monkeypatch.setattr(notify, '_gcm_migrated', True)
    monkeypatch.setattr(notify, '_icon_url', lambda: '/static/test-icon.ico')
    monkeypatch.setattr(notify, 'get_channel_layer', lambda: channel)
    monkeypatch.setattr(notify, 'send_mail', mail)
    with patch.object(type(GCMDevice.objects.all()), 'send_message', autospec=True) as fcm:
        fcm.side_effect = lambda qs, message: SimpleNamespace(success_count=qs.count(), responses=[])
        yield SimpleNamespace(fcm=fcm, channel=channel, mail=mail)
    cache.clear()


@pytest.fixture
def users(django_user_model):
    def create(name, active=True, **preferences):
        user = django_user_model.objects.create_user(username=name, email=f'{name}@example.test', is_active=active)
        for field, value in preferences.items():
            setattr(user.uzytkownik, field, value)
        user.uzytkownik.save()
        return user

    return create


@pytest.fixture
def payload():
    return notify.build_notification('Title', 'Body', 'https://example.test/events/1/', 'event-1')


def test_unsubscribe_disables_email_and_all_push_preferences(users):
    user = users(
        'unsubscribed',
        email_frequency='daily',
        push_notifications_obywatele=True,
        push_notifications_glosowania=True,
        push_notifications_chat=True,
        push_notifications_events=True,
        push_notifications_post=True,
        push_notifications_task=True,
        push_notifications_survey=True,
    )

    unsubscribe_user_notifications(user, source='email_link')
    profile = user.uzytkownik
    profile.refresh_from_db()

    assert profile.email_frequency == 'never'
    assert profile.notifications_unsubscribe_source == 'email_link'
    assert profile.notifications_unsubscribed_at is not None
    assert all(not getattr(profile, field) for field in notify._PUSH_FIELDS.values())
    assert profile.push_phone_enabled is False
    assert profile.push_computer_enabled is False


def test_gmail_one_click_unsubscribe_requires_exact_post_value(users, client):
    user = users('gmail')
    token = make_unsubscribe_token(user)
    url = reverse('unsubscribe_notifications', kwargs={'token': token})

    response = client.get(url)
    assert response.status_code == 200
    assert 'name="List-Unsubscribe" value="One-Click"' in response.content.decode()

    response = client.post(url, {'List-Unsubscribe': 'wrong'})
    assert response.status_code == 400
    user.uzytkownik.refresh_from_db()
    assert user.uzytkownik.notifications_unsubscribed_at is None

    response = client.post(url, {'List-Unsubscribe': 'One-Click'})
    assert response.status_code == 200
    user.uzytkownik.refresh_from_db()
    assert user.uzytkownik.email_frequency == 'never'


def test_subscription_email_contains_gmail_unsubscribe_headers(users, transport, settings):
    settings.SITE_PROTOCOL = 'https'
    user = users('headers')

    notify._dispatch_notification('Title', 'Body', '/events/1/', 'event-1', send_push=False, send_websocket=False, recipient_email=user.email, recipient_user=user)

    headers = transport.mail.call_args.kwargs['headers']
    assert headers['List-Unsubscribe'].startswith('<https://')
    assert headers['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'


def test_unsubscribed_user_does_not_receive_email_or_push(users, payload, transport):
    user = users('blocked')
    unsubscribe_user_notifications(user, source='gmail_one_click')

    assert notify.send_fcm_to_user_sync(user, payload, 'events') == 0
    notify._dispatch_notification('Title', 'Body', '/events/1/', 'event-1', send_push=False, send_websocket=False, recipient_email=user.email, recipient_user=user)

    transport.fcm.assert_not_called()
    transport.mail.assert_not_called()
