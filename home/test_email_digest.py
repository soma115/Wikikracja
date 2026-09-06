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
from chat.models import Message, MessageReadBy, Room
from core.models import ReadStatus
from core.services.feed import build_user_digest
from events.models import Event
from home.management.commands.send_email_digest import Command
from obywatele.models import CitizenActivity, Uzytkownik
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


@pytest.mark.django_db
def test_digest_private_room_title_is_personalized_for_each_member(digest_user, another_user):
    outsider = UserFactory(username='digest_outsider')
    room = Room.objects.create(title='Private digest', public=False)
    room.allowed.add(digest_user, another_user)
    Message.objects.create(room=room, sender=digest_user, text='From first member')
    Message.objects.create(room=room, sender=another_user, text='From second member')
    since = timezone.now() - td(hours=1)

    for user, other in ((digest_user, another_user), (another_user, digest_user), (outsider, None)):
        items = [item for item in build_user_digest(user, since) if item['content_type'] == 'room_messages' and item['room_id'] == room.pk]
        if other is None:
            assert items == []
        else:
            assert len(items) == 1
            assert items[0]['title'] == other.username
            assert items[0]['message_count'] == 1
            assert items[0]['url'] == f'/chat/#room_id={room.pk}'


@pytest.mark.django_db
def test_digest_ignores_read_state_and_includes_messages_at_since_boundary(digest_user, another_user):
    since = timezone.now() - td(hours=1)
    room = Room.objects.create(title='Read digest room', public=True)
    messages = [Message.objects.create(room=room, sender=another_user, text=text) for text in ('Old', 'Boundary', 'Newest')]
    for message, offset in zip(messages, (-1, 0, 1), strict=True):
        Message.objects.filter(pk=message.pk).update(time=since + td(seconds=offset))
        MessageReadBy.objects.create(message=message, user=digest_user)
    room.seen_by.add(digest_user)
    post = PostFactory(author=another_user)
    ReadStatus.objects.create(user=digest_user, content_type=ReadStatus.ContentType.POST, object_id=post.pk)

    items = build_user_digest(digest_user, since)
    chat_items = [item for item in items if item['content_type'] == 'room_messages' and item['room_id'] == room.pk]
    assert len(chat_items) == 1
    assert chat_items[0]['object_id'] == messages[-1].pk
    assert chat_items[0]['description'] == 'Newest'
    assert chat_items[0]['message_count'] == 2
    assert chat_items[0]['update_count'] == 2
    assert any(item['content_type'] == 'post' and item['object_id'] == post.pk for item in items)


@pytest.mark.django_db
def test_digest_omits_rooms_with_only_own_messages(digest_user):
    room = Room.objects.create(title='Only own messages', public=True)
    Message.objects.create(room=room, sender=digest_user, text='My message')

    items = build_user_digest(digest_user, timezone.now() - td(hours=1))

    assert not any(item['content_type'] == 'room_messages' and item['room_id'] == room.pk for item in items)


@pytest.mark.django_db
@pytest.mark.parametrize('room_flags', [{'archived': True}, {'is_inbox': True}])
def test_digest_omits_archived_rooms_and_guest_inbox(digest_user, another_user, room_flags):
    room = Room.objects.create(title='Excluded room', public=True)
    Message.objects.create(room=room, sender=another_user, text='Excluded message')
    Room.objects.filter(pk=room.pk).update(**room_flags)

    items = build_user_digest(digest_user, timezone.now() - td(hours=1))

    assert not any(item['content_type'] == 'room_messages' and item['room_id'] == room.pk for item in items)


@pytest.mark.django_db
def test_digest_groups_citizen_activities_by_user_and_keeps_latest(digest_user, another_user):
    since = timezone.now() - td(hours=1)
    CitizenActivity.objects.filter(uzytkownik__uid__in=(digest_user, another_user)).update(timestamp=since - td(seconds=1))
    activities = [
        CitizenActivity.objects.create(uzytkownik=user.uzytkownik, activity_type=activity_type)
        for user, activity_type in (
            (another_user, CitizenActivity.ActivityType.NEW_CANDIDATE),
            (another_user, CitizenActivity.ActivityType.USER_ACTIVATED),
            (digest_user, CitizenActivity.ActivityType.USER_ACTIVATED),
        )
    ]
    for index, activity in enumerate(activities):
        CitizenActivity.objects.filter(pk=activity.pk).update(timestamp=since + td(minutes=index + 1))

    items = [item for item in build_user_digest(digest_user, since) if item['content_type'] == 'citizen']

    assert [(item['author'].pk, item['object_id'], item['update_count']) for item in items] == [(digest_user.pk, activities[2].pk, 1), (another_user.pk, activities[1].pk, 2)]


@pytest.mark.django_db
def test_digest_sorts_upcoming_events_first_then_newest_posts(digest_user):
    now = timezone.now()
    later = Event.objects.create(title='Later', start_date=now + td(days=2), frequency='once', is_active=True)
    earlier = Event.objects.create(title='Earlier', start_date=now + td(days=1), frequency='once', is_active=True)
    older = PostFactory(author=digest_user)
    newer = PostFactory(author=digest_user)
    Post.objects.filter(pk=older.pk).update(updated=now - td(minutes=2))
    Post.objects.filter(pk=newer.pk).update(updated=now - td(minutes=1))
    expected = [('event', earlier.pk), ('event', later.pk), ('post', newer.pk), ('post', older.pk)]

    items = build_user_digest(digest_user, now - td(hours=1))

    assert [(item['content_type'], item['object_id']) for item in items if (item['content_type'], item['object_id']) in expected] == expected


@pytest.mark.django_db
@pytest.mark.parametrize('latest_anonymous', [False, True])
def test_digest_author_follows_latest_message_anonymity(digest_user, another_user, latest_anonymous):
    room = Room.objects.create(title='Digest privacy', public=True)
    since = timezone.now() - td(hours=1)
    previous = Message.objects.create(room=room, sender=another_user, anonymous=not latest_anonymous, text='Earlier message')
    latest = Message.objects.create(room=room, sender=another_user, anonymous=latest_anonymous, text='Latest message')
    Message.objects.filter(pk=previous.pk).update(time=since + td(minutes=1))
    Message.objects.filter(pk=latest.pk).update(time=since + td(minutes=2))

    item = next(item for item in build_user_digest(digest_user, since) if item['content_type'] == 'room_messages' and item['room_id'] == room.pk)
    assert item['object_id'] == latest.pk
    assert item['description'] == latest.text
    assert item['author'] == (None if latest_anonymous else another_user)
    assert item['message_count'] == item['update_count'] == 2
    context = Command()._build_digest_context(digest_user, [item])
    title = context['sections'][0]['items'][0]['title']
    assert (another_user.username in title) is (not latest_anonymous)
    assert room.title in title


@override_settings(**FAST_EMAIL_SETTINGS)
class SendEmailDigestCommandTest(TransactionTestCase):
    def _make_active_user(self, username, email):
        password = secrets.token_urlsafe(16)
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = True
        user.save()
        Uzytkownik.objects.filter(uid=user).update(email_frequency='daily', last_email_digest_at=FIXED_NOW - td(days=1))
        return user

    def _create_digest_post(self, author):
        """Create a fresh post that is guaranteed to appear in the digest."""
        from board.models import Post, PostCategory

        category = PostCategory.objects.create(name='Digest', priority=1)
        return Post.objects.create(title='Digest post', text='<p>body</p>', author=author, category=category, is_public=True)

    def _run_digest(self):
        with patch('home.management.commands.send_email_digest.timezone.now', return_value=FIXED_NOW):
            call_command('send_email_digest')
        _drain_threads()

    def test_digest_sends_email_to_due_user(self):
        user = self._make_active_user('citizen', 'citizen@example.com')
        self._create_digest_post(user)

        self._run_digest()

        emails = [e for e in mail.outbox if user.email in e.to]
        assert len(emails) == 1

    def test_digest_no_email_when_not_due(self):
        user = self._make_active_user('notdue', 'notdue@example.com')
        Uzytkownik.objects.filter(uid=user).update(email_frequency='daily', last_email_digest_at=FIXED_NOW)
        self._create_digest_post(user)

        self._run_digest()

        emails = [e for e in mail.outbox if user.email in e.to]
        assert len(emails) == 0

    def test_digest_no_email_when_frequency_never(self):
        user = self._make_active_user('never', 'never@example.com')
        Uzytkownik.objects.filter(uid=user).update(email_frequency='never')
        self._create_digest_post(user)

        self._run_digest()

        emails = [e for e in mail.outbox if user.email in e.to]
        assert len(emails) == 0

    def test_digest_updates_last_email_digest_at(self):
        user = self._make_active_user('updated', 'updated@example.com')
        past = FIXED_NOW - td(days=1)
        Uzytkownik.objects.filter(uid=user).update(email_frequency='daily', last_email_digest_at=past)
        self._create_digest_post(user)

        self._run_digest()

        profile = Uzytkownik.objects.get(uid=user)
        assert profile.last_email_digest_at > past
