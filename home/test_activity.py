import pytest
from django.urls import reverse
from django.utils import timezone

from board.models import Post
from chat.models import Message, MessageReadBy, Room
from home.models import ReadStatus
from tests.factories import PostCategoryFactory, PostFactory, UserFactory


@pytest.fixture
def activity_user(db):
    return UserFactory(username='activity', email='activity@example.com')


@pytest.mark.django_db
def test_activity_page_renders_read_toggle_buttons(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post = PostFactory(author=activity_user, category=category, title='Activity post', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.get(reverse('activity'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'feed-toggle-read' in content
    assert 'data-content-type="post"' in content
    assert f'data-object-id="{post.pk}"' in content
    assert 'window.MARK_UNREAD_URL' in content
    assert 'window.initActivityFeedToggleRead' in content


@pytest.mark.django_db
def test_mark_as_read_and_unread_endpoints_work_for_post(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post = PostFactory(author=activity_user, category=category, title='Toggle post', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.post(reverse('mark_as_read'), {'content_type': 'post', 'object_id': post.pk})
    assert response.status_code == 200
    assert response.json()['success'] is True
    assert ReadStatus.objects.filter(user=activity_user, content_type=ReadStatus.ContentType.POST, object_id=post.pk).exists()

    response = client.post(reverse('mark_unread'), {'content_type': 'post', 'object_id': post.pk})
    assert response.status_code == 200
    assert response.json()['success'] is True
    assert not ReadStatus.objects.filter(user=activity_user, content_type=ReadStatus.ContentType.POST, object_id=post.pk).exists()


@pytest.mark.django_db
def test_activity_shows_each_chat_message_as_separate_item(client, activity_user):
    client.force_login(activity_user)
    other = UserFactory(username='activity_other', email='activity_other@example.com')
    room = Room.objects.create(title='Activity test inbox', public=True)
    messages = [Message.objects.create(room=room, sender=other, text=f'Message {i}') for i in range(3)]

    response = client.get(reverse('activity'))
    content = response.content.decode()

    assert content.count('data-content-type="room_messages"') == 6
    assert all(f'data-object-id="{message.id}"' in content for message in messages)
    assert room.title in content
    assert f'Messages in {room.title}' not in content
    assert f'- <strong>{other.username}:' not in content
    assert 'chat-message-count' not in content


@pytest.mark.django_db
def test_chat_activity_items_are_read_per_message(client, activity_user):
    client.force_login(activity_user)
    other = UserFactory(username='activity_unread', email='activity_unread@example.com')
    room = Room.objects.create(title='Activity unread inbox', public=False)
    room.allowed.add(activity_user)
    messages = [Message.objects.create(room=room, sender=other, text=f'Message {i}') for i in range(3)]

    response = client.post(reverse('mark_as_read'), {'content_type': 'room_messages', 'object_id': messages[0].id})
    assert response.status_code == 200
    assert MessageReadBy.objects.filter(message=messages[0], user=activity_user).exists()

    response = client.post(reverse('mark_unread'), {'content_type': 'room_messages', 'object_id': messages[0].id})
    assert response.status_code == 200
    assert not MessageReadBy.objects.filter(message=messages[0], user=activity_user).exists()

    # Marking one message unread does not change the read state of its siblings.
    MessageReadBy.objects.create(message=messages[1], user=activity_user)
    response = client.get(reverse('activity'))
    content = response.content.decode()
    assert f'data-object-id="{messages[0].id}"' in content
    assert f'data-object-id="{messages[1].id}"' in content
