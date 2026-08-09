# Standard library imports
import json

# Third party imports
from captcha.models import CaptchaStore
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext as _

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

    def test_toggle_notifications_disables_notifications(self):
        # enabled=False → dodaje do muted_by
        self.client.force_login(self.user)
        response = self.client.post(reverse("chat:toggle_notifications"), data=json.dumps({"room_id": self.room.id, "enabled": False}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.user, self.room.muted_by.all())

    def test_toggle_notifications_enables_notifications(self):
        # enabled=True → usuwa z muted_by
        self.room.muted_by.add(self.user)
        self.client.force_login(self.user)
        self.client.post(reverse("chat:toggle_notifications"), data=json.dumps({"room_id": self.room.id, "enabled": True}), content_type="application/json")
        self.assertNotIn(self.user, self.room.muted_by.all())

    def test_toggle_notifications_missing_params_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("chat:toggle_notifications"), data=json.dumps({"room_id": self.room.id}), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_room_data_api_returns_json(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat:room_data", kwargs={"room_id": self.room.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

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


class ChatRoomAccessTest(TestCase):
    def setUp(self):
        self.member = make_user("member")
        self.outsider = make_user("outsider")
        self.private_room = Room.objects.create(title="Private", public=False)
        self.private_room.allowed.add(self.member)

    def test_room_data_accessible_by_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("chat:room_data", kwargs={"room_id": self.private_room.id}))
        self.assertEqual(response.status_code, 200)

    def test_room_data_returns_404_for_non_member(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("chat:room_data", kwargs={"room_id": self.private_room.id}))
        self.assertEqual(response.status_code, 404)


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
