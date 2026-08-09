# Third party imports
from captcha.models import CaptchaStore
from django.test import TestCase

# Local folder imports
from chat.forms import GuestMessageForm, RoomForm
from chat.models import Room


class RoomFormTest(TestCase):
    def test_valid_form(self):
        form = RoomForm(data={"title": "NowyPokój"})
        self.assertTrue(form.is_valid())

    def test_duplicate_title_different_case_is_rejected(self):
        Room.objects.create(title="Duplikat")
        form = RoomForm(data={"title": "duplikat"})
        self.assertFalse(form.is_valid())

    def test_duplicate_title_polish_non_ascii_is_rejected(self):
        # SQLite's LIKE/iexact only case-folds ASCII; Polish letters like Ś/ś, Ż/ż
        # slip through. Validation must use Python casefold, not DB-level iexact.
        Room.objects.create(title="Środa")
        form = RoomForm(data={"title": "środa"})
        self.assertFalse(form.is_valid())

    def test_rename_to_same_title_different_case_is_allowed(self):
        # editing own room: 'Ogólny' → 'ogólny' must not block itself
        room = Room.objects.create(title="Ogólny")
        form = RoomForm(data={"title": "ogólny"}, instance=room)
        self.assertTrue(form.is_valid())

    def test_duplicate_title_exact_case(self):
        Room.objects.create(title="Duplikat")
        form = RoomForm(data={"title": "Duplikat"})
        self.assertFalse(form.is_valid())

    def test_empty_title_invalid(self):
        form = RoomForm(data={"title": ""})
        self.assertFalse(form.is_valid())

    def test_title_too_long_invalid(self):
        form = RoomForm(data={"title": "A" * 256})
        self.assertFalse(form.is_valid())

    def test_inbox_rename_is_rejected(self):
        Room.objects.filter(is_inbox=True).delete()
        inbox = Room.objects.create(title="Inbox", public=True, protected=True, is_inbox=True)
        form = RoomForm(data={"title": "New Title"}, instance=inbox)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('title', code='inbox_rename_forbidden'))


class GuestMessageFormTest(TestCase):
    def _valid_captcha(self):
        return CaptchaStore.objects.create(challenge='test', response='test')

    def test_valid_form(self):
        store = self._valid_captcha()
        form = GuestMessageForm(data={'guest_email': 'guest@example.com', 'guest_name': 'Jan Kowalski', 'message': 'Hello', 'captcha_0': store.hashkey, 'captcha_1': 'test'})
        self.assertTrue(form.is_valid())

    def test_invalid_captcha(self):
        form = GuestMessageForm(data={'guest_email': 'guest@example.com', 'guest_name': 'Jan Kowalski', 'message': 'Hello', 'captcha_0': 'bad', 'captcha_1': 'bad'})
        self.assertFalse(form.is_valid())

    def test_missing_fields_invalid(self):
        form = GuestMessageForm(data={})
        self.assertFalse(form.is_valid())
