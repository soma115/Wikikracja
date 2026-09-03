"""Tests for the email activity digest and new push notification types."""

import secrets
import threading
from datetime import datetime
from datetime import timedelta as td
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from board.models import Post
from chat.models import Message, Room
from home.services.feed import build_user_digest
from obywatele.models import Uzytkownik
from tests.factories import PostCategoryFactory, PostFactory, UserFactory

FAST_EMAIL_SETTINGS = {'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend', 'EMAIL_SEND_DELAY_SECONDS': 0}

FIXED_NOW = timezone.make_aware(datetime(2026, 9, 2, 10, 0, 0))


def _drain_threads():
    main = threading.main_thread()
    for t in threading.enumerate():
        if t is main or not t.daemon:
            continue
        t.join(timeout=5)


@pytest.fixture
def digest_user(db):
    user = UserFactory(username='digestuser', email='digest@example.com')
    user.is_active = True
    user.save()
    Uzytkownik.objects.filter(uid=user).update(email_frequency='daily', last_email_digest_at=timezone.now() - td(days=1))
    return user


@pytest.fixture
def another_user(db):
    return UserFactory(username='another', email='another@example.com')


@pytest.mark.django_db
def test_build_user_digest_includes_chat_messages(digest_user, another_user):
    room = Room.objects.create(title='Test room', public=True)
    Message.objects.create(room=room, sender=another_user, text='Hello')

    since = timezone.now() - td(hours=1)
    items = build_user_digest(digest_user, since)

    chat_items = [i for i in items if i['content_type'] == 'room_messages']
    assert len(chat_items) == 1
    assert chat_items[0]['message_count'] == 1


@pytest.mark.django_db
def test_build_user_digest_chat_aggregates_multiple_messages(digest_user, another_user):
    room = Room.objects.create(title='Test room', public=True)
    Message.objects.create(room=room, sender=another_user, text='Hello')
    Message.objects.create(room=room, sender=another_user, text='World')

    since = timezone.now() - td(hours=1)
    items = build_user_digest(digest_user, since)

    chat_items = [i for i in items if i['content_type'] == 'room_messages']
    assert len(chat_items) == 1
    assert chat_items[0]['message_count'] == 2


@pytest.mark.django_db
def test_build_user_digest_filters_private_rooms(digest_user, another_user):
    public_room = Room.objects.create(title='Public', public=True)
    Message.objects.create(room=public_room, sender=another_user, text='Hello public')

    private_room = Room.objects.create(title='Private', public=False)
    private_room.allowed.add(another_user)
    Message.objects.create(room=private_room, sender=another_user, text='Secret')

    since = timezone.now() - td(hours=1)
    items = build_user_digest(digest_user, since)

    chat_items = [i for i in items if i['content_type'] == 'room_messages']
    assert len(chat_items) == 1
    assert 'Public' in chat_items[0]['title']


@pytest.mark.django_db
def test_build_user_digest_excludes_own_messages(digest_user, another_user):
    room = Room.objects.create(title='Test room', public=True)
    Message.objects.create(room=room, sender=digest_user, text='My own')
    Message.objects.create(room=room, sender=another_user, text='From them')

    since = timezone.now() - td(hours=1)
    items = build_user_digest(digest_user, since)

    chat_items = [i for i in items if i['content_type'] == 'room_messages']
    assert len(chat_items) == 1
    assert chat_items[0]['message_count'] == 1


@pytest.mark.django_db
def test_build_user_digest_excludes_items_before_since(digest_user):
    category = PostCategoryFactory()
    post = PostFactory(author=digest_user, category=category, title='Old post', text='<p>body</p>')
    old = timezone.now() - td(hours=2)
    Post.objects.filter(pk=post.pk).update(updated=old)

    since = timezone.now() - td(hours=1)
    items = build_user_digest(digest_user, since)

    old_post_items = [i for i in items if i['content_type'] == 'post' and i['object_id'] == post.pk]
    assert not old_post_items


@override_settings(**FAST_EMAIL_SETTINGS)
class SendEmailDigestCommandTest(TransactionTestCase):
    def _make_active_user(self, username, email):
        password = secrets.token_urlsafe(16)
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = True
        user.save()
        return user

    def _run_digest(self):
        with patch('home.management.commands.send_email_digest.timezone.now', return_value=FIXED_NOW):
            call_command('send_email_digest')
        _drain_threads()

    def test_digest_sends_email_to_due_user(self):
        user = self._make_active_user('citizen', 'citizen@example.com')
        Uzytkownik.objects.filter(uid=user).update(email_frequency='daily', last_email_digest_at=timezone.now() - td(days=1))

        room = Room.objects.create(title='Public', public=True)
        Message.objects.create(room=room, sender=user, text='Hello')

        self._run_digest()

        emails = [e for e in mail.outbox if user.email in e.to]
        assert len(emails) == 1

    def test_digest_no_email_when_not_due(self):
        user = self._make_active_user('notdue', 'notdue@example.com')
        Uzytkownik.objects.filter(uid=user).update(email_frequency='daily', last_email_digest_at=timezone.now())

        room = Room.objects.create(title='Public', public=True)
        Message.objects.create(room=room, sender=user, text='Hello')

        self._run_digest()

        emails = [e for e in mail.outbox if user.email in e.to]
        assert len(emails) == 0

    def test_digest_no_email_when_frequency_never(self):
        user = self._make_active_user('never', 'never@example.com')
        Uzytkownik.objects.filter(uid=user).update(email_frequency='never', last_email_digest_at=timezone.now() - td(days=1))

        room = Room.objects.create(title='Public', public=True)
        Message.objects.create(room=room, sender=user, text='Hello')

        self._run_digest()

        emails = [e for e in mail.outbox if user.email in e.to]
        assert len(emails) == 0

    def test_digest_updates_last_email_digest_at(self):
        user = self._make_active_user('updated', 'updated@example.com')
        past = timezone.now() - td(days=1)
        Uzytkownik.objects.filter(uid=user).update(email_frequency='daily', last_email_digest_at=past)

        room = Room.objects.create(title='Public', public=True)
        Message.objects.create(room=room, sender=user, text='Hello')

        self._run_digest()

        profile = Uzytkownik.objects.get(uid=user)
        assert profile.last_email_digest_at > past
