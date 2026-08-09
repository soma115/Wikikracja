"""
Tests for UpdateLastSeenMiddleware: aktualizuje user.last_login przy kazdym
requeście zalogowanego usera, ale max raz na 5 min (throttling przez cache).
"""

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.utils import timezone

from obywatele.middleware import UpdateLastSeenMiddleware


class UpdateLastSeenMiddlewareUnitTest(TestCase):
    """Unit tests: middleware wywolywany bezposrednio z RequestFactory."""

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()
        self.user = User.objects.create_user(username='test', password='secret')

    def _process(self, user):
        request = self.factory.get('/')
        request.user = user
        middleware = UpdateLastSeenMiddleware(lambda r: 'response')
        return middleware(request)

    def test_authenticated_request_updates_last_login(self):
        before = timezone.now()
        self._process(self.user)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login, "last_login should be set after first authenticated request")
        self.assertGreaterEqual(self.user.last_login, before)

    def test_throttle_prevents_second_update_within_window(self):
        self._process(self.user)
        self.user.refresh_from_db()
        first_login = self.user.last_login

        self._process(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_login, first_login, "Second request within throttle window must NOT update last_login")

    def test_update_after_throttle_window_expires(self):
        self._process(self.user)
        # Symuluj ze pierwszy update byl dawno, zeby porownanie bylo deterministyczne
        past = timezone.now() - timedelta(minutes=10)
        User.objects.filter(pk=self.user.pk).update(last_login=past)
        cache.clear()  # symuluje wygasniecie TTL klucza throttlingu

        self._process(self.user)
        self.user.refresh_from_db()
        self.assertGreater(self.user.last_login, past, "After cache expiry, last_login should update again")

    def test_anonymous_user_does_not_break(self):
        response = self._process(AnonymousUser())
        self.assertEqual(response, 'response', "Middleware must pass through anonymous users without error")

    def test_returns_response_for_authenticated(self):
        response = self._process(self.user)
        self.assertEqual(response, 'response', "Middleware must return the response from get_response")

    def test_does_not_overwrite_other_fields(self):
        self.user.first_name = 'TestName'
        self.user.save()
        self._process(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'TestName', "QuerySet.update(last_login=...) must only touch the last_login column")

    def test_inactive_user_does_not_update_last_login(self):
        """User z is_active=False nie powinien aktualizowac last_login -
        chroni komende count_citizens przed blokowaniem usuwania zdezaktywowanych userow."""
        self.user.is_active = False
        self.user.save()
        User.objects.filter(pk=self.user.pk).update(last_login=None)

        self._process(self.user)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.last_login, "Inactive users must not have last_login updated by middleware")


class UpdateLastSeenMiddlewareDbEfficiencyTest(TestCase):
    """Pilnuje kontraktu 'nieobciazania serwera': 0 queries gdy throttled, 1 gdy update."""

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()
        self.user = User.objects.create_user(username='dbuser', password='secret')

    def _process(self, user):
        request = self.factory.get('/')
        request.user = user
        middleware = UpdateLastSeenMiddleware(lambda r: 'response')
        return middleware(request)

    def test_update_is_single_query(self):
        """Aktualizacja last_login musi byc pojedynczym UPDATE (nie SELECT+UPDATE z save())."""
        with self.assertNumQueries(1):
            self._process(self.user)

    def test_throttled_request_does_no_db_queries(self):
        """Drugi request w oknie throttlingu nie moze uderzyc do DB."""
        self._process(self.user)  # initial - hits DB
        with self.assertNumQueries(0):
            self._process(self.user)  # throttled - 0 queries


class UpdateLastSeenIntegrationTest(TestCase):
    """End-to-end: middleware faktycznie zmienia kolejnosc na liscie obywateli."""

    def setUp(self):
        cache.clear()
        self.old_user = User.objects.create_user(username='old', password='secret', is_active=True)
        self.fresh_user = User.objects.create_user(username='fresh', password='secret', is_active=True)
        # Stary user ma last_login sprzed tygodnia
        User.objects.filter(pk=self.old_user.pk).update(last_login=timezone.now() - timedelta(days=7))

    def test_recently_seen_user_appears_first_in_sort(self):
        """Po request przez middleware, fresh_user jest na gorze listy sortowanej po -last_login."""
        self.client.force_login(self.fresh_user)
        # force_login emituje signal user_logged_in ktory tez aktualizuje last_login;
        # cofamy to zeby test naprawde weryfikowal middleware, a nie signal Djanga.
        past = timezone.now() - timedelta(days=14)
        User.objects.filter(pk=self.fresh_user.pk).update(last_login=past)
        cache.clear()

        response = self.client.get('/obywatele/?sort=-last_login')
        self.assertEqual(response.status_code, 200)

        usernames = [u.username for u in response.context['uid']]
        self.assertEqual(usernames[0], 'fresh', f"Expected 'fresh' first (middleware should update last_login), got: {usernames}")


class FormalLoginBypassThrottleTest(TestCase):
    """Logowanie formalne (signal user_logged_in) musi aktualizowac last_login
    niezaleznie od cache'a throttlingu naszego middleware'a."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='loginer', password='secret')

    def test_formal_login_updates_last_login_even_when_throttle_active(self):
        # Symuluj ze nasze middleware niedawno aktualizowalo (cache key istnieje)
        cache.set(f'last_seen:{self.user.pk}', True, 300)

        success = self.client.login(username='loginer', password='secret')
        self.assertTrue(success, "Login should succeed")

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login, "Django signal user_logged_in must update last_login even when our throttle is active")
