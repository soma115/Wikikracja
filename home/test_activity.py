import pytest
from django.urls import reverse
from django.utils import timezone

from board.models import Post
from chat.models import Message, MessageReadBy, Room
from core.models import FeedBookmark, ReadStatus
from tests.factories import DecyzjaFactory, PostCategoryFactory, PostFactory, UserFactory


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
    assert 'tw-feed-toggle' in content
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

    assert content.count('data-content-type="room_messages"') == 9
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


@pytest.mark.django_db
def test_toggle_bookmark_endpoint_works(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post = PostFactory(author=activity_user, category=category, title='Bookmark post', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.post(reverse('toggle_bookmark'), {'content_type': 'post', 'object_id': post.pk})
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert data['is_bookmarked'] is True
    assert FeedBookmark.objects.filter(user=activity_user, content_type='post', object_id=post.pk).exists()

    response = client.post(reverse('toggle_bookmark'), {'content_type': 'post', 'object_id': post.pk})
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert data['is_bookmarked'] is False
    assert not FeedBookmark.objects.filter(user=activity_user, content_type='post', object_id=post.pk).exists()


@pytest.mark.django_db
def test_activity_page_renders_bookmark_toggle_buttons(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post = PostFactory(author=activity_user, category=category, title='Bookmark visible post', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.get(reverse('activity'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-action="bookmark"' in content
    assert 'data-action="read"' in content
    assert 'window.TOGGLE_BOOKMARK_URL' in content
    assert 'window.initActivityFeedToggleBookmark' in content


@pytest.mark.django_db
def test_activity_row_is_div_with_data_url(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post = PostFactory(author=activity_user, category=category, title='Div row post', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.get(reverse('activity'))
    assert response.status_code == 200
    content = response.content.decode()
    assert '<div class="tw-feed-row' in content
    assert 'data-url="' in content
    assert f'data-object-id="{post.pk}"' in content
    assert '<a href="' in content


@pytest.mark.django_db
def test_mark_all_read_endpoint_works(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post = PostFactory(author=activity_user, category=category, title='Mark all post', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.post(reverse('mark_all_read'))
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert data['marked_count'] >= 1
    assert ReadStatus.objects.filter(user=activity_user, content_type=ReadStatus.ContentType.POST, object_id=post.pk).exists()


@pytest.mark.django_db
def test_activity_filter_unread_and_bookmarks_intersection(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post_unread_bookmarked = PostFactory(author=activity_user, category=category, title='Unread bookmarked', text='<p>body</p>')
    post_unread = PostFactory(author=activity_user, category=category, title='Unread not bookmarked', text='<p>body</p>')
    post_bookmarked = PostFactory(author=activity_user, category=category, title='Read bookmarked', text='<p>body</p>')
    post_read = PostFactory(author=activity_user, category=category, title='Read not bookmarked', text='<p>body</p>')
    for post in [post_unread_bookmarked, post_unread, post_bookmarked, post_read]:
        Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    ReadStatus.objects.create(user=activity_user, content_type=ReadStatus.ContentType.POST, object_id=post_bookmarked.pk)
    ReadStatus.objects.create(user=activity_user, content_type=ReadStatus.ContentType.POST, object_id=post_read.pk)

    FeedBookmark.objects.create(user=activity_user, content_type='post', object_id=post_unread_bookmarked.pk)
    FeedBookmark.objects.create(user=activity_user, content_type='post', object_id=post_bookmarked.pk)

    response = client.get(reverse('activity'), {'unread': '1', 'bookmarks': '1'})
    content = response.content.decode()
    assert 'Unread bookmarked' in content
    assert 'Unread not bookmarked' not in content
    assert 'Read bookmarked' not in content
    assert 'Read not bookmarked' not in content


@pytest.mark.django_db
def test_activity_filter_unread_by_content_type(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post_unread = PostFactory(author=activity_user, category=category, title='Unread post', text='<p>body</p>')
    DecyzjaFactory(author=activity_user, title='Unread decision')
    Post.objects.filter(pk=post_unread.pk).update(updated=timezone.now())

    response = client.get(reverse('activity'), {'unread': '1', 'type': 'post', 'filtered': '1'})
    content = response.content.decode()
    assert 'Unread post' in content
    assert 'Unread decision' not in content


@pytest.mark.django_db
def test_activity_filter_bookmarks_by_content_type(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post_bookmarked = PostFactory(author=activity_user, category=category, title='Bookmarked post', text='<p>body</p>')
    decision_bookmarked = DecyzjaFactory(author=activity_user, title='Bookmarked decision')
    Post.objects.filter(pk=post_bookmarked.pk).update(updated=timezone.now())

    FeedBookmark.objects.create(user=activity_user, content_type='post', object_id=post_bookmarked.pk)
    FeedBookmark.objects.create(user=activity_user, content_type='decision', object_id=decision_bookmarked.pk)

    response = client.get(reverse('activity'), {'bookmarks': '1', 'type': 'post', 'filtered': '1'})
    content = response.content.decode()
    assert 'Bookmarked post' in content
    assert 'Bookmarked decision' not in content


@pytest.mark.django_db
def test_activity_filter_form_preserves_unread_and_bookmarks(client, activity_user):
    client.force_login(activity_user)
    response = client.get(reverse('activity'), {'unread': '1', 'bookmarks': '1'})
    content = response.content.decode()
    assert '<input type="hidden" name="unread" value="1">' in content
    assert '<input type="hidden" name="bookmarks" value="1">' in content
