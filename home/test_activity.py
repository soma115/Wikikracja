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
def test_chat_message_count_badge_hidden_when_room_is_read(client, activity_user):
    client.force_login(activity_user)
    other = UserFactory(username='activity_other', email='activity_other@example.com')
    room = Room.objects.create(title='Activity test inbox', public=True)
    for i in range(3):
        Message.objects.create(room=room, sender=other, text=f'Message {i}')

    # Unread room: badge should be rendered visible
    response = client.get(reverse('activity'))
    content = response.content.decode()
    assert 'chat-message-count' in content
    assert 'badge' in content and room.title in content

    # Read room: badge should be hidden
    room.seen_by.add(activity_user)
    response = client.get(reverse('activity'))
    content = response.content.decode()
    assert 'chat-message-count' in content
    # The badge element exists but is hidden via d-none
    assert 'chat-message-count' in content and 'd-none' in content


@pytest.mark.django_db
def test_chat_badge_not_shown_when_all_messages_read_and_marked_unread(client, activity_user):
    """Marking a room as unread in the activity feed should not show a message
    count badge when all recent messages have already been read."""
    client.force_login(activity_user)
    other = UserFactory(username='activity_unread', email='activity_unread@example.com')
    room = Room.objects.create(title='Activity unread inbox', public=False)
    room.allowed.add(activity_user)
    for i in range(5):
        Message.objects.create(room=room, sender=other, text=f'Message {i}')

    # Simulate that the user opened the room and all messages were marked as read.
    for msg in Message.objects.filter(room=room):
        MessageReadBy.objects.get_or_create(message=msg, user=activity_user)
    room.seen_by.add(activity_user)

    # Mark the room as unread from the activity feed.
    response = client.post(reverse('mark_unread'), {'content_type': 'room_messages', 'object_id': room.id})
    assert response.status_code == 200
    assert response.json()['success'] is True
    assert activity_user not in room.seen_by.all()

    response = client.get(reverse('activity'))
    content = response.content.decode()
    assert 'data-content-type="room_messages"' in content
    assert room.title in content
    # No new messages, so the count badge should not be rendered.
    assert 'chat-message-count' not in content
