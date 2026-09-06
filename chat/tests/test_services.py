from unittest.mock import MagicMock, patch

import firebase_admin
from channels.db import database_sync_to_async
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from firebase_admin import messaging as firebase_messaging
from push_notifications.models import GCMDevice

from chat.models import Message
from chat.services import ChatRepository, extract_mentions, get_avatar_url
from chat.tests.utils import make_user
from tasks.tests.utils import make_task
from zzz.notifications import build_notification, send_fcm_to_user_sync


class _UserWithoutProfile:
    """Stub user where accessing .uzytkownik raises (simulating broken/missing relation)."""

    @property
    def uzytkownik(self):
        raise AttributeError("no related profile")


class GetAvatarUrlTest(TestCase):
    def test_returns_none_when_avatar_not_uploaded(self):
        # post_save signal auto-creates Uzytkownik; avatar field is empty by default.
        user = make_user("noavatar")
        self.assertIsNone(get_avatar_url(user))

    def test_returns_none_when_user_is_none(self):
        self.assertIsNone(get_avatar_url(None))

    def test_returns_none_when_uzytkownik_attribute_raises(self):
        self.assertIsNone(get_avatar_url(_UserWithoutProfile()))

    def test_returns_url_when_avatar_uploaded(self):
        user = make_user("withavatar")
        user.uzytkownik.avatar = SimpleUploadedFile("test.png", b"fake-bytes", content_type="image/png")
        user.uzytkownik.save()
        result = get_avatar_url(user)
        self.assertIsNotNone(result)
        self.assertIn("avatars/", result)
        self.assertTrue(result.endswith(".png"))


class ExtractMentionsTest(TestCase):
    def test_extracts_single_mention(self):
        self.assertEqual(extract_mentions("Cześć @alice"), {"alice"})

    def test_extracts_multiple_mentions(self):
        self.assertEqual(extract_mentions("@alice i @bob"), {"alice", "bob"})

    def test_returns_empty_when_no_mentions(self):
        self.assertEqual(extract_mentions("Bez wzmianki"), set())

    def test_ignores_email_like_text(self):
        self.assertEqual(extract_mentions("alice@example.com"), set())

    def test_handles_br_tags(self):
        self.assertEqual(extract_mentions("Cześć<br>@alice"), {"alice"})

    def test_deduplicates_mentions(self):
        self.assertEqual(extract_mentions("@alice @alice"), {"alice"})


class CanPostInRoomTest(TestCase):
    def setUp(self):
        self.coordinator = make_user("coordinator")
        self.helper = make_user("helper")
        self.approved = make_user("approved")
        self.stranger = make_user("stranger")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, team_mode=True)
        from tasks.models import TaskVote

        TaskVote.objects.create(task=self.task, user=self.helper, value=1)
        TaskVote.objects.create(task=self.task, user=self.approved, value=1)
        self.task.approve_helper(self.approved)

        self.room = self.task.chat_room

    async def test_coordinator_can_post(self):
        repo = ChatRepository(self.coordinator)
        self.assertTrue(await repo.can_post_in_room(self.room))

    async def test_approved_helper_can_post(self):
        repo = ChatRepository(self.approved)
        self.assertTrue(await repo.can_post_in_room(self.room))

    async def test_unapproved_helper_cannot_post(self):
        repo = ChatRepository(self.helper)
        self.assertFalse(await repo.can_post_in_room(self.room))

    async def test_stranger_cannot_post(self):
        repo = ChatRepository(self.stranger)
        self.assertFalse(await repo.can_post_in_room(self.room))

    async def test_old_task_allows_everyone(self):
        old_task = await database_sync_to_async(make_task)(created_by=self.coordinator, team_mode=False)
        repo = ChatRepository(self.stranger)
        self.assertTrue(await repo.can_post_in_room(old_task.chat_room))


class TaskRoomVoterNamesTest(TestCase):
    """W pokojach zadań głosy na wiadomościach są jawne — payload zawiera nicki głosujących."""

    def setUp(self):
        self.author = make_user("msgauthor")
        self.voter_up = make_user("upvoter")
        self.voter_down = make_user("downvoter")
        self.task = make_task(created_by=self.author)
        self.room = self.task.chat_room
        self.msg = Message.objects.create(room=self.room, sender=self.author, text="Propozycja")
        self.msg.reactions = {'upvotes': [self.voter_up.id], 'downvotes': [self.voter_down.id]}
        self.msg.save(update_fields=['reactions'])
        self.repo = ChatRepository(self.author)

    async def test_batch_includes_voter_names_when_include_voters(self):
        batch = await self.repo.get_recent_messages_batch(self.room.id, self.author.id, include_voters=True)
        msg = batch['messages'][-1]
        self.assertEqual(msg['upvoters'], ['upvoter'])
        self.assertEqual(msg['downvoters'], ['downvoter'])

    async def test_batch_omits_voter_names_by_default(self):
        batch = await self.repo.get_recent_messages_batch(self.room.id, self.author.id)
        msg = batch['messages'][-1]
        self.assertNotIn('upvoters', msg)
        self.assertNotIn('downvoters', msg)

    async def test_get_vote_voters_returns_names(self):
        voters = await self.repo.get_vote_voters(self.msg.id)
        self.assertEqual(voters, {'upvoters': ['upvoter'], 'downvoters': ['downvoter']})

    async def test_get_vote_voters_missing_message(self):
        voters = await self.repo.get_vote_voters(999999)
        self.assertEqual(voters, {'upvoters': [], 'downvoters': []})

    async def test_voter_lists_skip_deleted_users(self):
        await database_sync_to_async(self.voter_up.delete)()
        voters = await self.repo.get_vote_voters(self.msg.id)
        self.assertEqual(voters, {'upvoters': [], 'downvoters': ['downvoter']})


class SendPushNotificationSyncTest(TestCase):
    """Regression tests for the FCM message built by send_push_notification_sync."""

    def setUp(self):
        self.user = make_user("pushuser")
        self.repo = ChatRepository(self.user)

        self.mock_queryset = MagicMock()
        self.mock_queryset.exists.return_value = True
        self.mock_queryset.send_message.return_value = MagicMock(success_count=1, responses=[MagicMock(success=True)])

    async def test_builds_full_fcm_message(self):
        """The message must contain top-level notification, data payload and webpush notification."""
        with patch("zzz.notifications.GCMDevice") as mock_gcm:
            mock_gcm.objects.filter.return_value = self.mock_queryset
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                await self.repo.send_push_notification_sync(self.user, "Room: Test", "Sender: Alice", "https://example.com/chat#room_id=1", 1, room_name="Test")

        self.assertTrue(self.mock_queryset.send_message.called)
        message = self.mock_queryset.send_message.call_args[0][0]
        self.assertIsInstance(message, firebase_messaging.Message)

        # Top-level notification lets the FCM SDK display the notification automatically.
        self.assertEqual(message.notification.title, "Room: Test")
        self.assertEqual(message.notification.body, "Sender: Alice")

        # Data payload is used by onMessage and onBackgroundMessage.
        self.assertEqual(message.data["title"], "Room: Test")
        self.assertEqual(message.data["body"], "Sender: Alice")
        self.assertEqual(message.data["room_id"], "1")
        self.assertEqual(message.data["room_name"], "Test")
        self.assertEqual(message.data["click_action"], "https://example.com/chat#room_id=1")
        self.assertIn("favicon.ico", message.data["icon"])

        # webpush.notification is needed for the killed-browser/PWA case.
        webpush_notification = message.webpush.notification
        self.assertEqual(webpush_notification.title, "Room: Test")
        self.assertEqual(webpush_notification.body, "Sender: Alice")
        self.assertEqual(webpush_notification.tag, "chat-1")
        self.assertTrue(webpush_notification.require_interaction)
        self.assertEqual(webpush_notification.data["room_id"], "1")
        self.assertEqual(webpush_notification.data["click_action"], "https://example.com/chat#room_id=1")
        self.assertIn("favicon.ico", webpush_notification.icon)
        self.assertIn("favicon.ico", webpush_notification.badge)

        # webpush.fcm_options.link handles notification click.
        self.assertEqual(message.webpush.fcm_options.link, "https://example.com/chat#room_id=1")


class FCMDeviceDeactivationTest(TestCase):
    """Regression tests for automatic deactivation of dead FCM tokens."""

    def setUp(self):
        self.user = make_user("deactivationuser")
        self.device = GCMDevice.objects.create(user=self.user, registration_id="dead_token", active=True, cloud_message_type="FCM")

    def test_unregistered_token_gets_deactivated(self):
        """django-push-notifications must mark an UnregisteredError token inactive."""
        unregistered = firebase_messaging.UnregisteredError("Token unregistered")
        response = firebase_messaging.SendResponse(None, unregistered)
        batch = firebase_messaging.BatchResponse([response])

        with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
            with patch.object(firebase_messaging, "send_each", return_value=batch):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")

        self.device.refresh_from_db()
        self.assertFalse(self.device.active)


class FCMDeviceTypeFilterTest(TestCase):
    """Regression tests for per-device-type (phone/computer) push filtering."""

    def setUp(self):
        self.user = make_user("filteruser")

    def _mock_queryset(self):
        qs = MagicMock()
        qs.count.return_value = 1
        qs.send_message.return_value = MagicMock(success_count=1, responses=[MagicMock(success=True)])
        qs.exclude.return_value = qs
        return qs

    def _assert_send_called(self, mock_gcm, expected_exclude_call):
        # _migrate_legacy_gcm_devices() filters legacy GCM rows first, so the main
        # filter is the second call.
        filter_calls = [c for c in mock_gcm.objects.filter.call_args_list if c.kwargs.get("cloud_message_type") == "FCM"]
        self.assertEqual(len(filter_calls), 1)
        mock_gcm.objects.filter.assert_any_call(user=self.user, active=True, cloud_message_type="FCM")
        mock_gcm.objects.filter.return_value.exclude.assert_called_once_with(**expected_exclude_call)
        mock_gcm.objects.filter.return_value.send_message.assert_called_once()

    def test_phone_disabled_excludes_mobile_and_tablet(self):
        self.user.uzytkownik.push_phone_enabled = False
        self.user.uzytkownik.save()

        with patch("zzz.notifications.GCMDevice") as mock_gcm:
            mock_gcm.objects.filter.return_value = self._mock_queryset()
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")
        self._assert_send_called(mock_gcm, {"name__in": ("mobile", "tablet")})

    def test_computer_disabled_excludes_desktop(self):
        self.user.uzytkownik.push_computer_enabled = False
        self.user.uzytkownik.save()

        with patch("zzz.notifications.GCMDevice") as mock_gcm:
            mock_gcm.objects.filter.return_value = self._mock_queryset()
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")
        self._assert_send_called(mock_gcm, {"name": "desktop"})

    def test_both_disabled_excludes_both_device_types(self):
        self.user.uzytkownik.push_phone_enabled = False
        self.user.uzytkownik.push_computer_enabled = False
        self.user.uzytkownik.save()

        with patch("zzz.notifications.GCMDevice") as mock_gcm:
            qs = self._mock_queryset()
            mock_gcm.objects.filter.return_value = qs
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")
        mock_gcm.objects.filter.assert_any_call(user=self.user, active=True, cloud_message_type="FCM")
        self.assertEqual(qs.exclude.call_count, 2)
        qs.exclude.assert_any_call(name__in=("mobile", "tablet"))
        qs.exclude.assert_any_call(name="desktop")
        qs.send_message.assert_called_once()
