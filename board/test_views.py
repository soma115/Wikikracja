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

    def test_board_stepper_filters_documents(self):
        self._post('Public')
        Post.objects.create(title='Mine', text='Mine text', author=self.user, is_private=True)
        Post.objects.create(title='Important', text='Important text', author=self.user, is_important=True)
        deleted = self._post('Deleted')
        deleted.is_deleted = True
        deleted.save(update_fields=['is_deleted'])

        response = self.client.get(reverse('board:start'), {'tab': 'mine'})
        self.assertEqual([post.title for post in response.context['ordered_posts']], ['Mine'])
        self.assertEqual(response.context['board_tab_counts'], {'mine': 1, 'public': 1, 'important': 1, 'trash': 1})

    def test_delete_moves_document_to_trash_and_restore_recovers_it(self):
        post = self._post('Movable')

        delete_response = self.client.post(reverse('board:delete_post', args=[post.pk]))
        self.assertRedirects(delete_response, reverse('board:start') + '?tab=trash')
        post.refresh_from_db()
        self.assertTrue(post.is_deleted)

        trash_response = self.client.get(reverse('board:start'), {'tab': 'trash'})
        self.assertContains(trash_response, 'Movable')

        restore_response = self.client.post(reverse('board:restore_post', args=[post.pk]))
        self.assertRedirects(restore_response, reverse('board:start') + '?tab=mine')
        post.refresh_from_db()
        self.assertFalse(post.is_deleted)

    def test_detail_uses_shared_card_and_sanitizes_document_content(self):
        post = self._post('Safe document')
        post.text = '<b>Visible formatting</b><script>alert("unsafe")</script>'
        post.save(update_fields=['text'])

        response = self.client.get(reverse('board:view_post', args=[post.pk]))

        self.assertContains(response, 'tw-card')
        self.assertNotContains(response, 'tw-board-post-card')
        self.assertContains(response, '<b>Visible formatting</b>', html=True)
        self.assertNotContains(response, '<script>alert("unsafe")</script>')
