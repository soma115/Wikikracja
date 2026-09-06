# Standard library imports
import json

# Third party imports
from captcha.models import CaptchaStore
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext as _
from push_notifications.models import GCMDevice

# Local folder imports
from chat.models import Message, Room
from chat.tests.utils import make_user


class ChatViewsTest(TestCase):
    def setUp(self):
        # self.client is provided by default in Django TestCase
        self.user = make_user("chatuser")
        self.room = Room.objects.create(title="PublicRoom", public=True)
        self.room.allowed.add(self.user)

    def test_chat_view_requires_login(self):
        response = self.client.get(reverse("chat:chat"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_chat_view_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:chat"))
        self.assertEqual(response.status_code, 200)

    def test_chat_view_includes_document_rooms(self):
        from board.models import Post

        post = Post.objects.create(title="Board doc", text="<p>content</p>", author=self.user)
        self.assertIsNotNone(post.chat_room)

        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:chat"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(post.chat_room, response.context["posts_tree_active"])

    def test_add_room_get_requires_login(self):
        response = self.client.get(reverse("chat:add_room"))
        self.assertEqual(response.status_code, 302)

    def test_add_room_get_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:add_room"))
        self.assertEqual(response.status_code, 200)

    def test_add_room_post_creates_room_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("chat:add_room"), {"title": "NowyPokój"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Room.objects.filter(title="NowyPokój").exists())

    def test_add_room_post_duplicate_title_shows_form_errors(self):
        self.client.force_login(self.user)
        self.client.post(reverse("chat:add_room"), {"title": "Powtórzony"})
        response = self.client.post(reverse("chat:add_room"), {"title": "powtórzony"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Room.objects.filter(title="powtórzony").exists())

    def test_add_room_post_empty_title_shows_form_errors(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("chat:add_room"), {"title": ""})
        self.assertEqual(response.status_code, 200)

    def test_upload_image_requires_login(self):
        # upload_image wymaga zalogowania — anonim jest przekierowany do logowania
        response = self.client.post("/chat/upload/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response["Location"])

    def test_upload_image_authenticated_returns_json(self):
        self.client.force_login(self.user)
        response = self.client.post("/chat/upload/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("filenames", response.json())

    def test_open_dm_creates_room_when_missing(self):
        self.client.force_login(self.user)
        other = make_user("other")
        self.assertIsNone(Room.find_with_users(self.user, other))

        response = self.client.get(reverse("chat:open_dm", kwargs={"pk": other.pk}))

        room = Room.find_with_users(self.user, other)
        self.assertIsNotNone(room)
        self.assertFalse(room.public)
        self.assertEqual(set(room.allowed.all()), {self.user, other})
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"#room_id={room.id}", response["Location"])

    def test_open_dm_uses_existing_room(self):
        self.client.force_login(self.user)
        other = make_user("other")
        existing = Room.objects.create(title="chatuser-other", public=False)
        existing.allowed.set([self.user, other])

        response = self.client.get(reverse("chat:open_dm", kwargs={"pk": other.pk}))

        self.assertEqual(Room.objects.filter(public=False, allowed=self.user).filter(allowed=other).count(), 1)
        self.assertIn(f"#room_id={existing.id}", response["Location"])

    def test_open_dm_reactivates_archived_room(self):
        self.client.force_login(self.user)
        other = make_user("other")
        archived = Room.objects.create(title="chatuser-other", public=False, archived=True)
        archived.allowed.set([self.user, other])

        response = self.client.get(reverse("chat:open_dm", kwargs={"pk": other.pk}))

        archived.refresh_from_db()
        self.assertFalse(archived.archived)
        self.assertIn(f"#room_id={archived.id}", response["Location"])

    def test_open_dm_self_redirects_to_chat_root(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:open_dm", kwargs={"pk": self.user.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("#room_id=", response["Location"])


class RenameRoomViewTest(TestCase):
    def setUp(self):
        self.user = make_user("renamer")
        self.public_room = Room.objects.create(title="StaraNazwa", public=True, protected=False)
        self.public_room.allowed.add(self.user)
        self.protected_room = Room.objects.create(title="Chroniony", public=True, protected=True)
        self.protected_room.allowed.add(self.user)
        self.private_room = Room.objects.create(title="renamer-other", public=False)
        self.private_room.allowed.add(self.user)

    def _rename(self, room, title):
        return self.client.post(reverse("chat:rename_room", kwargs={"room_id": room.id}), data=json.dumps({"title": title}), content_type="application/json")

    def test_rename_requires_login(self):
        response = self._rename(self.public_room, "Nowa")
        self.assertEqual(response.status_code, 302)

    def test_rename_public_room_succeeds(self):
        self.client.force_login(self.user)
        response = self._rename(self.public_room, "NowaNazwa")
        self.assertEqual(response.status_code, 200)
        self.public_room.refresh_from_db()
        self.assertEqual(self.public_room.title, "NowaNazwa")

    def test_rename_protected_room_denied(self):
        self.client.force_login(self.user)
        response = self._rename(self.protected_room, "Zmieniony")
        self.assertEqual(response.status_code, 404)
        self.protected_room.refresh_from_db()
        self.assertEqual(self.protected_room.title, "Chroniony")

    def test_rename_private_room_denied(self):
        self.client.force_login(self.user)
        response = self._rename(self.private_room, "Zmieniony")
        self.assertEqual(response.status_code, 404)

    def test_rename_to_duplicate_title_returns_400(self):
        Room.objects.create(title="JuzIstnieje", public=True)
        self.client.force_login(self.user)
        response = self._rename(self.public_room, "JuzIstnieje")
        self.assertEqual(response.status_code, 400)

    def test_rename_to_same_name_succeeds(self):
        self.client.force_login(self.user)
        response = self._rename(self.public_room, "StaraNazwa")
        self.assertEqual(response.status_code, 200)

    def test_rename_empty_title_returns_400(self):
        self.client.force_login(self.user)
        response = self._rename(self.public_room, "")
        self.assertEqual(response.status_code, 400)

    def test_rename_non_member_denied(self):
        outsider = make_user("outsider2")
        self.client.force_login(outsider)
        response = self._rename(self.public_room, "Próba")
        self.assertEqual(response.status_code, 403)

    def test_rename_get_method_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:rename_room", kwargs={"room_id": self.public_room.id}))
        self.assertEqual(response.status_code, 405)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class GuestMessageViewTest(TestCase):
    def setUp(self):
        cache.clear()
        Room.objects.filter(is_inbox=True).delete()
        self.inbox = Room.objects.create(title="Inbox", public=True, protected=True, is_inbox=True)

    def _captcha_data(self):
        store = CaptchaStore.objects.create(challenge='test', response='test')
        return {'guest_email': 'guest@example.com', 'guest_name': 'Jan Kowalski', 'message': 'Hello from a guest', 'captcha_0': store.hashkey, 'captcha_1': 'test'}

    def test_guest_message_get(self):
        response = self.client.get(reverse("chat:guest_message"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, _("Send a message"))

    def test_guest_message_post_creates_message(self):
        response = self.client.post(reverse("chat:guest_message"), self._captcha_data())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('sent'))
        self.assertTrue(Message.objects.filter(room=self.inbox, anonymous=True).exists())
        message = Message.objects.get(room=self.inbox, anonymous=True)
        self.assertEqual(message.guest_email, 'guest@example.com')
        self.assertEqual(message.guest_name, 'Jan Kowalski')
        self.assertIn('Jan Kowalski', message.text)
        self.assertIn('guest@example.com', message.text)
        self.assertIn('Hello from a guest', message.text)

    def test_guest_message_post_invalid_captcha(self):
        data = self._captcha_data()
        data['captcha_1'] = 'wrong'
        response = self.client.post(reverse("chat:guest_message"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Message.objects.filter(room=self.inbox).exists())

    def test_guest_message_rate_limit(self):
        for i in range(3):
            data = self._captcha_data()
            data['message'] = f'Message {i}'
            self.client.post(reverse("chat:guest_message"), data)
        self.assertEqual(Message.objects.filter(room=self.inbox).count(), 3)

        # Fourth message should be rejected by the rate limiter
        data = self._captcha_data()
        data['message'] = 'Message 4'
        response = self.client.post(reverse("chat:guest_message"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.filter(room=self.inbox).count(), 3)


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PushDeviceRegisterViewTest(TestCase):
    """Regression tests for FCM device registration allowing multiple active devices per user."""

    def setUp(self):
        cache.clear()
        self.user = make_user("pushuser")
        self.other = make_user("otherpush")

    def _register(self, token, device_type=None, display_mode=None, user=None):
        self.client.force_login(user or self.user)
        payload = {'platform': 'fcm', 'registration_id': token}
        if device_type:
            payload['device_type'] = device_type
        if display_mode:
            payload['display_mode'] = display_mode
        return self.client.post(reverse("chat:push_register"), data=json.dumps(payload), content_type="application/json")

    def test_register_creates_active_fcm_device(self):
        response = self._register('token1')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        device = GCMDevice.objects.get(user=self.user, registration_id='token1')
        self.assertTrue(device.active)
        self.assertEqual(device.cloud_message_type, 'FCM')

    def test_register_second_device_keeps_first_active(self):
        """Multiple devices for the same user can be active simultaneously."""
        self._register('token1')
        self._register('token2')
        active = GCMDevice.objects.filter(user=self.user, active=True)
        self.assertEqual(active.count(), 2)
        self.assertEqual(sorted(active.values_list('registration_id', flat=True)), ['token1', 'token2'])

    def test_register_same_token_twice_does_not_duplicate(self):
        self._register('token1')
        self._register('token1')
        self.assertEqual(GCMDevice.objects.filter(user=self.user, registration_id='token1').count(), 1)

    def test_register_reassigns_token_from_other_user(self):
        GCMDevice.objects.create(user=self.other, registration_id='shared_token', active=True, cloud_message_type='FCM')
        response = self._register('shared_token')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GCMDevice.objects.filter(user=self.other).exists())
        device = GCMDevice.objects.get(user=self.user, registration_id='shared_token')
        self.assertTrue(device.active)

    def test_register_saves_device_type(self):
        response = self._register('token1', device_type='mobile')
        self.assertEqual(response.status_code, 200)
        device = GCMDevice.objects.get(user=self.user, registration_id='token1')
        self.assertEqual(device.name, 'mobile')

    def test_register_saves_display_mode(self):
        response = self._register('token1', device_type='mobile', display_mode='standalone')
        self.assertEqual(response.status_code, 200)
        device = GCMDevice.objects.get(user=self.user, registration_id='token1')
        self.assertEqual(device.application_id, 'standalone')

    def test_unregister_deactivates_device(self):
        self._register('token1')
        self.client.force_login(self.user)
        response = self.client.post(reverse("chat:push_unregister"), data=json.dumps({'platform': 'fcm', 'registration_id': 'token1'}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        device = GCMDevice.objects.get(user=self.user, registration_id='token1')
        self.assertFalse(device.active)
