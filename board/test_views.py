from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from board.models import Post, PostCategory

User = get_user_model()


class BoardDetailNavigationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='board-user', password='pass')
        self.category = PostCategory.objects.create(name='Documents')
        self.other_category = PostCategory.objects.create(name='Other')
        self.client.force_login(self.user)

    def _post(self, title, category=None):
        return Post.objects.create(title=title, text=f'{title} text', author=self.user, category=category, is_public=True)

    def test_detail_navigation_preserves_sort_and_search_context(self):
        first = self._post('Alpha')
        middle = self._post('Bravo')
        last = self._post('Charlie')

        response = self.client.get(reverse('board:view_post', args=[middle.pk]), {'sort': 'title', 'order': 'asc', 'q': 'a'})

        self.assertEqual(response.context['previous_url'], f"{reverse('board:view_post', args=[first.pk])}?sort=title&order=asc&q=a")
        self.assertEqual(response.context['next_url'], f"{reverse('board:view_post', args=[last.pk])}?sort=title&order=asc&q=a")

    def test_detail_navigation_respects_selected_categories(self):
        first = self._post('Alpha', self.category)
        current = self._post('Bravo', self.category)
        self._post('Charlie', self.other_category)

        response = self.client.get(reverse('board:view_post', args=[current.pk]), {'category': self.category.pk})

        self.assertEqual(response.context['previous_url'], reverse('board:view_post', args=[first.pk]) + f'?category={self.category.pk}')
        self.assertIsNone(response.context['next_url'])
