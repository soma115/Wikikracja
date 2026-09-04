import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ankiety.models import Survey
from board.models import Post
from chat.models import Room
from events.models import Event
from glosowania.models import Decyzja
from tasks.models import Task


class LinkTitlesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', first_name='Alice', last_name='Example')
        self.other = User.objects.create_user(username='bob')
        self.endpoint = reverse('link_titles')

    def resolve(self, *urls):
        response = self.client.post(self.endpoint, json.dumps({'urls': urls}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return response.json()['titles']

    def test_resolves_supported_links_for_authenticated_user(self):
        self.client.force_login(self.user)
        task = Task.objects.create(title='Activity title', description='Description', created_by=self.user)
        decision = Decyzja.objects.create(title='Voting title', tresc='Text', author=self.user)
        survey = Survey.objects.create(title='Survey title', end_date=timezone.now() + timezone.timedelta(days=1), author=self.user)
        event = Event.objects.create(title='Event title', start_date=timezone.now() + timezone.timedelta(days=1))
        post = Post.objects.create(title='Document title', text='Text', author=self.user, slug='document-title')
        room = Room.objects.create(title='alice-bob', public=False)
        room.allowed.add(self.user, self.other)

        urls = [
            f'http://testserver{reverse("tasks:detail", kwargs={"pk": task.pk})}',
            reverse('glosowania:details', kwargs={'pk': decision.pk}),
            reverse('ankiety:detail', kwargs={'pk': survey.pk}),
            reverse('events:detail', kwargs={'pk': event.pk}),
            reverse('board:view_post', kwargs={'pk': post.pk}),
            reverse('board:view_post_by_slug', kwargs={'slug': post.slug}),
            reverse('obywatele:obywatele_szczegoly', kwargs={'pk': self.other.pk}),
            f'/chat#room_id={room.pk}',
        ]

        titles = self.resolve(*urls)

        self.assertEqual(
            titles,
            {urls[0]: task.title, urls[1]: decision.title, urls[2]: survey.title, urls[3]: event.title, urls[4]: post.title, urls[5]: post.title, urls[6]: self.other.username, urls[7]: self.other.username},
        )

    def test_anonymous_user_only_sees_public_content(self):
        public_post = Post.objects.create(title='Public document', text='Text', author=self.user, is_public=True)
        private_post = Post.objects.create(title='Private document', text='Text', author=self.user, is_public=False)
        public_event = Event.objects.create(title='Public event', start_date=timezone.now(), is_public=True)
        private_event = Event.objects.create(title='Private event', start_date=timezone.now(), is_public=False)
        task = Task.objects.create(title='Members only', description='Description', created_by=self.user)
        urls = [
            reverse('board:view_post', kwargs={'pk': public_post.pk}),
            reverse('board:view_post', kwargs={'pk': private_post.pk}),
            reverse('events:detail', kwargs={'pk': public_event.pk}),
            reverse('events:detail', kwargs={'pk': private_event.pk}),
            reverse('tasks:detail', kwargs={'pk': task.pk}),
        ]

        titles = self.resolve(*urls)

        self.assertEqual(titles, {urls[0]: public_post.title, urls[2]: public_event.title})

    def test_does_not_disclose_inaccessible_room_or_external_url(self):
        self.client.force_login(self.user)
        room = Room.objects.create(title='Secret room', public=False)
        room.allowed.add(self.other)
        public_room = Room.objects.create(title='Public room', public=True)
        room_url = f'/chat/#room_id={room.pk}&message_id=123'
        public_room_url = f'/chat#room_id={public_room.pk}'
        external_url = f'https://example.com/tasks/{room.pk}/'

        self.assertEqual(self.resolve(room_url, public_room_url, external_url), {public_room_url: public_room.title})

    def test_rejects_invalid_payload(self):
        response = self.client.post(self.endpoint, json.dumps({'urls': 'not-a-list'}), content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'titles': {}})
