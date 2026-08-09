from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from chat.models import Message, Room
from chat.services import get_unread_count_for_user
from home.services.feed import FEED_CACHE_KEY, generate_feed_items


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

    def tearDown(self):
        cache.clear()

    def test_badge_href_is_unconditional_view_unread(self):
        """Niezaleznie od chat_unread_count, href badge'a zawsze prowadzi do
        ?view=unread (chat.js sam obsluguje 0-wynikow przez empty state)."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '?view=unread')
        self.assertNotContains(response, '?unread=1')
        self.assertNotContains(response, '?notify=no-unread')

    def test_badge_style_accentuated_when_unread(self):
        """Sam href jest staly, ale styl badge'a (.chat-unread-btn) musi
        byc obecny w label'u tylko gdy sa nieprzeczytane."""
        room = Room.objects.create(title='Pokój A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.user, text='hej', room=room)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'chat-unread-btn')

    def test_badge_style_neutral_without_unread(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertNotContains(response, 'chat-unread-btn')

    def test_dynamic_badge_js_uses_view_unread_in_both_branches(self):
        """JS w home.html aktualizuje badge.href po nadejsciu WS event'u — w obu
        galeziach (count > 0 i count == 0) musi prowadzic do ?view=unread."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertContains(response, "'?view=unread'")
        self.assertNotContains(response, "'?notify=no-unread'")
        self.assertNotContains(response, "'?unread=1'")


class UnreadCountConsistencyTest(TestCase):
    """
    Licznik nieprzeczytanych pokoi czatu musi byc taki sam niezaleznie od tego,
    czy jest liczony z poziomu feed (home/activity) czy chat (services).
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='consistent', password='pass')

    def tearDown(self):
        cache.clear()

    def _unread_chat_rooms(self, user):
        """Liczba nieprzeczytanych pozycji room_messages w feed."""
        return sum(1 for item in generate_feed_items(user) if item['content_type'] == 'room_messages' and not item['is_read'])

    def test_feed_and_chat_agree_when_unread(self):
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.user, text='hej', room=room)

        self.assertEqual(get_unread_count_for_user(self.user), 1)
        self.assertEqual(self._unread_chat_rooms(self.user), 1)

    def test_feed_and_chat_agree_after_see_room(self):
        """Gdy user wejdzie do pokoju w czacie (room.seen_by.add), feed
        musi od razu widziec ten pokoj jako przeczytany."""
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.user, text='hej', room=room)

        room.seen_by.add(self.user)

        self.assertEqual(get_unread_count_for_user(self.user), 0)
        self.assertEqual(self._unread_chat_rooms(self.user), 0)

    def test_mark_as_read_from_feed_updates_chat_count(self):
        """Oznaczenie pokoju jako przeczytany z feed musi uniewazniac
        cache czatu, zeby oba liczniki byly spojne."""
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.user, text='hej', room=room)

        self.client.force_login(self.user)
        response = self.client.post(reverse('mark_as_read'), {'content_type': 'room_messages', 'object_id': room.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_unread_count_for_user(self.user), 0)
        self.assertEqual(self._unread_chat_rooms(self.user), 0)

    def test_mark_unread_from_feed_updates_chat_count(self):
        """Oznaczenie pokoju jako nieprzeczytany z feed musi uniewazniac
        cache czatu."""
        room = Room.objects.create(title='Pokoj A', public=False)
        room.allowed.add(self.user)
        Message.objects.create(sender=self.user, text='hej', room=room)
        room.seen_by.add(self.user)

        self.client.force_login(self.user)
        response = self.client.post(reverse('mark_unread'), {'content_type': 'room_messages', 'object_id': room.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_unread_count_for_user(self.user), 1)
        self.assertEqual(self._unread_chat_rooms(self.user), 1)
