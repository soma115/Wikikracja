from types import SimpleNamespace

from django.test import SimpleTestCase

from zzz.templatetags.citizen_filters import citizen_color_class, user_display_name, user_initials


def _user(username='jkowalski', first_name='', last_name=''):
    """Minimalni user z interfejsem Django User potrzebnym helperom."""
    return SimpleNamespace(username=username, first_name=first_name, last_name=last_name, get_full_name=lambda: f'{first_name} {last_name}'.strip())


class UserDisplayNameTest(SimpleTestCase):
    def test_prefers_full_name(self):
        assert user_display_name(_user(first_name='Jan', last_name='Kowalski')) == 'Jan Kowalski'

    def test_falls_back_to_single_name_part(self):
        assert user_display_name(_user(first_name='Jan')) == 'Jan'
        assert user_display_name(_user(last_name='Kowalski')) == 'Kowalski'

    def test_falls_back_to_username(self):
        assert user_display_name(_user()) == 'jkowalski'

    def test_accepts_profile_object_via_uid(self):
        profile = SimpleNamespace(uid=_user(first_name='Anna', last_name='Nowak'))
        assert user_display_name(profile) == 'Anna Nowak'

    def test_none_and_empty(self):
        assert user_display_name(None) == ''


class UserInitialsTest(SimpleTestCase):
    def test_first_and_last_name(self):
        assert user_initials(_user(first_name='Jan', last_name='Kowalski')) == 'JK'

    def test_only_first_name_uses_first_two_letters(self):
        assert user_initials(_user(first_name='Jan')) == 'JA'

    def test_only_last_name_uses_first_two_letters(self):
        assert user_initials(_user(last_name='Kowalski')) == 'KO'

    def test_no_names_falls_back_to_username(self):
        assert user_initials(_user()) == 'JK'
        assert user_initials(_user(username='ala')) == 'AL'

    def test_accepts_profile_object_via_uid(self):
        profile = SimpleNamespace(uid=_user(first_name='Anna', last_name='Nowak'))
        assert user_initials(profile) == 'AN'

    def test_none_and_empty(self):
        assert user_initials(None) == ''


class CitizenColorStabilityTest(SimpleTestCase):
    def test_color_depends_only_on_username(self):
        assert citizen_color_class('jkowalski') == citizen_color_class('jkowalski')
        assert citizen_color_class('jkowalski').startswith('tw-citizen-color-')
