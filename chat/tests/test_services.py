from unittest.mock import MagicMock, patch

import firebase_admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from firebase_admin import messaging as firebase_messaging

from chat.services import ChatRepository, extract_mentions, get_avatar_url
from chat.tests.utils import make_user


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
