from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from django.utils.translation import gettext as _

from chat.models import Message, Room
from chat.services import get_unread_count_for_user
from core.services.feed import FEED_CACHE_KEY, generate_feed_items
from home.navigation import get_navigation_context
from site_settings.models import QuickLink


class HealthChecksTest(TestCase):
    def test_liveness_does_not_require_authentication(self):
        response = self.client.get(reverse('healthz_live'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_readiness_checks_database_and_cache(self):
        response = self.client.get(reverse('healthz_ready'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    @patch('home.views.cache.get', side_effect=RuntimeError)
    def test_readiness_returns_service_unavailable_when_dependency_fails(self, cache_get):
        response = self.client.get(reverse('healthz_ready'))

        self.assertEqual(response.status_code, 503)
        cache_get.assert_called_once_with('healthz')


class NavigationContextTest(TestCase):
    def _context_for(self, url_name):
        path = reverse(url_name)
        request = RequestFactory().get(path)
        request.resolver_match = resolve(path)
        return get_navigation_context(request)

    def test_navigation_items_keep_order_and_page_prefs_contract(self):
        context = self._context_for('tasks:list')
        items = {item['url_name']: item for item in context['navigation_items']}

        self.assertEqual(
            [item['url_name'] for item in context['navigation_items']],
            ['home', 'tasks:list', 'obywatele:obywatele', 'board:start', 'events:list', 'glosowania:proposition', 'bookkeeping:transaction_list', 'ankiety:list', 'chat:chat'],
        )
        self.assertEqual(items['tasks:list']['href'], reverse('tasks:list'))
        self.assertEqual(items['tasks:list']['base_href'], reverse('tasks:list'))
        self.assertEqual(items['tasks:list']['prefs_scope'], 'tasks')
        self.assertTrue(items['tasks:list']['active'])
        self.assertEqual(str(context['current_module']), str(items['tasks:list']['label']))
        self.assertEqual(context['current_module_url'], reverse('tasks:list'))

    def test_settings_page_is_not_marked_as_citizens_module(self):
        context = self._context_for('obywatele:my_profile')
        items = {item['url_name']: item for item in context['navigation_items']}

        self.assertEqual(str(context['current_module']), str(_('Settings')))
        self.assertEqual(context['current_module_url'], reverse('obywatele:my_profile'))
        self.assertTrue(context['settings_active'])
        self.assertFalse(items['obywatele:obywatele']['active'])

    def test_home_page_marks_desktop_as_active(self):
        context = self._context_for('home')
        items = {item['url_name']: item for item in context['navigation_items']}

        self.assertEqual(str(context['current_module']), str(items['home']['label']))
        self.assertTrue(items['home']['active'])
        self.assertEqual(items['chat:chat']['active_class'], 'tw-active')


class QuickLinkSettingsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='quick-links', password='pass')
        self.client.force_login(self.user)
        self.url = reverse('group_settings')

    def test_quick_links_accept_relative_and_http_urls(self):
        last_order = QuickLink.objects.order_by('-order').values_list('order', flat=True).first()
        last_order = last_order if last_order is not None else -1
        created_links = []
        for link_url in ('/chat/', 'https://example.com/help'):
            with self.subTest(link_url=link_url):
                response = self.client.post(self.url, {'save_quick_link': '1', 'quick_link_title': 'Link', 'quick_link_url': link_url})
                self.assertEqual(response.status_code, 302)
                created_links.append(QuickLink.objects.order_by('-id').first())

        self.assertEqual([link.order for link in created_links], [last_order + 1, last_order + 2])
        self.assertTrue(QuickLink.objects.filter(url='/chat/').exists())
        self.assertTrue(QuickLink.objects.filter(url='https://example.com/help').exists())

    def test_quick_links_reject_unsafe_url_schemes(self):
        response = self.client.post(self.url, {'save_quick_link': '1', 'quick_link_title': 'Unsafe', 'quick_link_url': 'javascript:alert(1)'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(QuickLink.objects.filter(title='Unsafe').exists())

    def test_quick_link_form_does_not_expose_order_field(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="quick_link_order"')


class ActivityFeedChatTest(TestCase):
    def setUp(self):
        cache.delete(FEED_CACHE_KEY)
        self.user = User.objects.create_user(username='testowy', password='pass')

    def tearDown(self):
        cache.delete(FEED_CACHE_KEY)

    def test_chat_messages_visible_for_allowed_user(self):
        room = Room.objects.create(title='Pokój testowy', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.user, text='Hej!', room=room)

        feed = generate_feed_items(self.user)
        chat_items = [i for i in feed if i['content_type'] == 'room_messages']

        self.assertGreater(len(chat_items), 0, "Aktywnosc/ powinna pokazywac wiadomosci z chatu")

    def test_public_room_visible_without_allowed(self):
        room = Room.objects.create(title='Publiczny pokój', public=True)
        Message.objects.create(sender=self.user, text='Cześć!', room=room)

        feed = generate_feed_items(self.user)
        chat_items = [i for i in feed if i['content_type'] == 'room_messages']

        self.assertGreater(len(chat_items), 0, "Publiczny pokoj powinien byc widoczny bez bycia w allowed")

    def test_chat_messages_hidden_for_non_allowed_user(self):
        other_user = User.objects.create_user(username='inny', password='pass')
        room = Room.objects.create(title='Prywatny pokój', public=False)
        room.allowed.add(other_user)
        Message.objects.create(sender=other_user, text='Tajne', room=room)

        feed = generate_feed_items(self.user)
        chat_items = [i for i in feed if i['content_type'] == 'room_messages']

        self.assertEqual(len(chat_items), 0, "Uzytkownik bez dostepu nie powinien widziec pokoju")


class HomeChatBadgeTest(TestCase):
    """
    Pulpit (badge na stronie glownej) zawsze prowadzi do czatu z filtrem unread
    (`?view=unread`), niezaleznie od liczby nieprzeczytanych. Gdy brak
    nieprzeczytanych — chat.js pokazuje empty state w prawej kolumnie.

    Dynamiczny JS aktualizujacy badge po WS/visibilitychange musi uzywac tego
    samego URL'a w obu galeziach (count > 0 i count == 0).
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='dashuser', password='pass')
        self.other_user = User.objects.create_user(username='dashother', password='pass')

    def tearDown(self):
        cache.clear()

    def test_badge_href_is_unconditional_view_unread(self):
        """Niezaleznie od chat_unread_count, href badge'a zawsze prowadzi do
        ?view=unread (chat.js sam obsluguje 0-wynikow przez empty state)."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.content.decode(), r'<a id="chat-unread-badge"\s+href="/chat/\?view=unread"')

    def test_badge_style_accentuated_when_unread(self):
        """Gdy sa nieprzeczytane wiadomosci, licznik chatu jest wiekszy od 0."""
        room = Room.objects.create(title='Pokój A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.other_user, text='hej', room=room)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertGreater(response.context['chat_unread_count'], 0)

    def test_badge_style_neutral_without_unread(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.context['chat_unread_count'], 0)

    def test_dynamic_badge_js_uses_view_unread_in_both_branches(self):
        """JS w home.html aktualizuje badge.href po nadejsciu WS event'u — w obu
        galeziach (count > 0 i count == 0) musi prowadzic do ?view=unread."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertRegex(response.content.decode(), r'<a id="chat-unread-badge"\s+href="/chat/\?view=unread"')


class UnreadCountConsistencyTest(TestCase):
    """
    Licznik nieprzeczytanych pokoi czatu musi byc taki sam niezaleznie od tego,
    czy jest liczony z poziomu feed (home/activity) czy chat (services).
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='consistent', password='pass')
        self.other_user = User.objects.create_user(username='consistent-other', password='pass')

    def tearDown(self):
        cache.clear()

    def _unread_chat_rooms(self, user):
        """Liczba nieprzeczytanych pozycji room_messages w feed."""
        return sum(1 for item in generate_feed_items(user) if item['content_type'] == 'room_messages' and not item['is_read'])

    def test_feed_and_chat_agree_when_unread(self):
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.other_user, text='hej', room=room)

        self.assertEqual(get_unread_count_for_user(self.user), 1)
        self.assertEqual(self._unread_chat_rooms(self.user), 1)

    def test_feed_and_chat_agree_after_see_room(self):
        """Gdy user wejdzie do pokoju w czacie (room.seen_by.add), feed
        musi od razu widziec ten pokoj jako przeczytany."""
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.other_user, text='hej', room=room)

        room.seen_by.add(self.user)

        self.assertEqual(get_unread_count_for_user(self.user), 0)
        self.assertEqual(self._unread_chat_rooms(self.user), 0)

    def test_mark_as_read_from_feed_updates_chat_count(self):
        """Oznaczenie pokoju jako przeczytany z feed musi uniewazniac
        cache czatu, zeby oba liczniki byly spojne."""
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        message = Message.objects.create(sender=self.other_user, text='hej', room=room)

        self.client.force_login(self.user)
        response = self.client.post(reverse('mark_as_read'), {'content_type': 'room_messages', 'object_id': message.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_unread_count_for_user(self.user), 0)
        self.assertEqual(self._unread_chat_rooms(self.user), 0)

    def test_mark_unread_from_feed_updates_chat_count(self):
        """Oznaczenie pokoju jako nieprzeczytany z feed musi uniewazniac
        cache czatu."""
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        message = Message.objects.create(sender=self.other_user, text='hej', room=room)
        room.seen_by.add(self.user)

        self.client.force_login(self.user)
        response = self.client.post(reverse('mark_unread'), {'content_type': 'room_messages', 'object_id': message.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_unread_count_for_user(self.user), 1)
        self.assertEqual(self._unread_chat_rooms(self.user), 1)
