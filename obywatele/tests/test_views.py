"""
Testy widoku set_user_language: wybór języka musi działać dla NIEzalogowanych
(strona startowa + cały proces zakładania konta), z trwałością przez cookie
`django_language`, a dla zalogowanych dodatkowo zapisywać się do profilu.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from obywatele.auth_backends import CaseInsensitiveEmailBackend


class DebugSkipAuthTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='debug-auth', email='debug@example.com', password='correct-password')
        self.backend = CaseInsensitiveEmailBackend()

    @override_settings(DEBUG=False, DEBUG_SKIP_AUTH=True)
    def test_skip_auth_is_ignored_outside_debug_mode(self):
        authenticated = self.backend.authenticate(None, username=self.user.email, password='wrong-password')

        self.assertIsNone(authenticated)

    @override_settings(DEBUG=True, DEBUG_SKIP_AUTH=True)
    def test_skip_auth_still_works_in_debug_mode(self):
        authenticated = self.backend.authenticate(None, username=self.user.email, password='wrong-password')

        self.assertEqual(authenticated, self.user)


class SetLanguageAnonymousTest(TestCase):
    """Niezalogowany użytkownik może wybrać język — utrwalony w cookie."""

    def setUp(self):
        self.url = reverse('obywatele:set_language')
        self.cookie_name = settings.LANGUAGE_COOKIE_NAME

    def test_anonymous_can_set_language_sets_cookie(self):
        response = self.client.post(self.url, {'language': 'en', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        self.assertIn(self.cookie_name, response.cookies)
        self.assertEqual(response.cookies[self.cookie_name].value, 'en')

    def test_anonymous_invalid_language_ignored(self):
        response = self.client.post(self.url, {'language': 'xx', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        # Nieobsługiwany kod języka w ogóle nie dotyka cookie (gałąź else widoku)
        self.assertNotIn(self.cookie_name, response.cookies)

    def test_external_next_is_rejected(self):
        """Otwarty endpoint nie może być wektorem open-redirect."""
        response = self.client.post(self.url, {'language': 'en', 'next': 'https://evil.example/'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')


class SetLanguageAuthenticatedTest(TestCase):
    """Zalogowany użytkownik: wybór zapisuje się do profilu ORAZ do cookie."""

    def setUp(self):
        self.url = reverse('obywatele:set_language')
        self.cookie_name = settings.LANGUAGE_COOKIE_NAME
        self.user = User.objects.create_user(username='lang', password='secret', is_active=True)
        self.client.force_login(self.user)

    def test_authenticated_persists_to_profile_and_cookie(self):
        response = self.client.post(self.url, {'language': 'en', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        self.user.uzytkownik.refresh_from_db()
        self.assertEqual(self.user.uzytkownik.language, 'en')
        self.assertEqual(response.cookies[self.cookie_name].value, 'en')

    def test_authenticated_auto_resets_profile_and_deletes_cookie(self):
        # najpierw ustaw konkretny język
        self.client.post(self.url, {'language': 'en', 'next': '/'})
        # potem "Auto (browser)" = pusty język
        response = self.client.post(self.url, {'language': '', 'next': '/'})

        self.assertEqual(response.status_code, 302)
        self.user.uzytkownik.refresh_from_db()
        self.assertEqual(self.user.uzytkownik.language, '')
        # "Auto" usuwa cookie języka — wygaszenie sygnalizowane przez max-age=0
        self.assertIn(self.cookie_name, response.cookies)
        self.assertEqual(response.cookies[self.cookie_name]['max-age'], 0)


class LanguageSwitcherRenderTest(TestCase):
    """Przełącznik języka jest widoczny przez CAŁY anonimowy flow zakładania konta.

    Wszystkie te strony rozszerzają home/base.html i biegną dla niezalogowanego
    użytkownika, więc dzielą anon-topbar ze switcherem. Asercja na każdym kroku
    pilnuje właściwego wymogu: gdyby ktoś przeniósł switcher poza anon-topbar albo
    dał @login_required na onboarding, te testy to złapią.
    """

    def setUp(self):
        self.switcher_url = reverse('obywatele:set_language')

    def test_home_anonymous_renders_language_switcher(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.switcher_url)

    def test_signup_renders_language_switcher(self):
        response = self.client.get(reverse('account_signup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.switcher_url)

    def test_onboarding_renders_language_switcher(self):
        # Onboarding biegnie bez @login_required — dostęp z onboarding_user_id w sesji.
        user = User.objects.create_user(username='onb', email='onb@example.com', password='secret', is_active=False)
        session = self.client.session
        session['onboarding_user_id'] = user.id
        session.save()

        response = self.client.get(reverse('obywatele:onboarding_details'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.switcher_url)


class CitizenZalozonoTemplateTest(TestCase):
    """Widok citizen_zalozono musi renderować inny szablon dla żądań AJAX i zwykłych."""

    def setUp(self):
        self.user = User.objects.create_user(username='zalozono', password='secret', is_active=True)
        self.url = reverse('obywatele:citizen_zalozono', kwargs={'pk': self.user.pk})

    def test_non_ajax_renders_full_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'obywatele/citizen_zalozono.html')

    def test_ajax_renders_partial_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'obywatele/_citizen_zalozono_partial.html')
