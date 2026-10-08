import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from board.models import Post
from bookkeeping.models import Asset, Partner, Transaction
from chat.models import Message, MessageReadBy, Room
from core.models import FeedBookmark, ReadStatus
from core.services.feed import FEED_CACHE_KEY, generate_feed_items, generate_feed_raw
from glosowania.models import Argument
from tasks.models import Task, TaskVote
from tests.factories import DecyzjaFactory, PostCategoryFactory, PostFactory, UserFactory


@pytest.fixture
def activity_user(db):
    return UserFactory(username='activity', email='activity@example.com')


@pytest.mark.django_db
def test_activity_includes_new_voting_arguments_and_invalidates_feed_cache(client, activity_user):
    author = UserFactory(username='argument_author', email='argument-author@example.com')
    decision = DecyzjaFactory(author=author, title='Argument activity proposal')
    cache.delete(FEED_CACHE_KEY)
    assert not any(item['content_type'] == 'decision' and item['description'].startswith('Argument:') for item in generate_feed_raw())

    argument = Argument.objects.create(decyzja=decision, author=author, argument_type='FOR', content='A new supporting argument')

    raw_items = generate_feed_raw()
    argument_item = next(item for item in raw_items if item['content_type'] == 'decision' and item['object_id'] == decision.pk and item.get('activity_kind') == 'argument')
    assert argument_item['argument_id'] == argument.pk
    assert 'A new supporting argument' in argument_item['description']

    client.force_login(activity_user)
    response = client.get(reverse('activity'))
    content = response.content.decode()
    assert f'data-object-id="{decision.pk}"' in content
    assert 'A new supporting argument' in content


@pytest.mark.django_db
def test_activity_includes_new_votes_on_actions_and_invalidates_feed_cache(client, activity_user):
    coordinator = UserFactory(username='activity_task_coordinator', email='activity-task-coordinator@example.com')
    helper = UserFactory(username='activity_task_helper', email='activity-task-helper@example.com')
    task = Task.objects.create(title='Activity task vote', description='Description', created_by=coordinator, assigned_to=coordinator)
    cache.delete(FEED_CACHE_KEY)
    generate_feed_raw()

    TaskVote.objects.create(task=task, user=helper, value=TaskVote.Value.UP)
    client.force_login(activity_user)
    response = client.get(reverse('activity'))

    item = next(item for item in generate_feed_raw() if item['content_type'] == 'task' and item['object_id'] == task.pk and item.get('activity_kind') == 'vote')
    assert item['vote_id'] is not None
    assert item['author'] == helper
    assert response.status_code == 200
    assert str(gettext('Wants to help')) in response.content.decode()


@pytest.mark.django_db
def test_activity_page_renders_read_toggle_buttons(client, activity_user):
    client.force_login(activity_user)
    category = PostCategoryFactory()
    post = PostFactory(author=activity_user, category=category, title='Activity post', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.get(reverse('activity'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'tw-current' in content
    assert 'Aktywność' in content
    assert 'id="topbar-subtitle"' not in content
    assert 'tw-feed-toggle' in content
    assert 'data-content-type="post"' in content
    assert f'data-object-id="{post.pk}"' in content
    assert 'window.MARK_UNREAD_URL' in content
    assert 'window.initActivityFeedToggleRead' in content


@pytest.mark.django_db
def test_activity_renders_author_avatar(client, activity_user, settings, tmp_path):
    client.force_login(activity_user)
    settings.MEDIA_ROOT = tmp_path
    activity_user.uzytkownik.avatar = SimpleUploadedFile('activity-avatar.png', b'fake-image', content_type='image/png')
    activity_user.uzytkownik.save(update_fields=['avatar'])
    post = PostFactory(author=activity_user, title='Activity avatar', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.get(reverse('activity'))

    assert 'src="/media/avatars/activity-avatar.png"' in response.content.decode()


@pytest.mark.django_db
def test_activity_documents_show_subtitle_without_content(client, activity_user):
    client.force_login(activity_user)
    post = PostFactory(author=activity_user, title='Activity document', subtitle='Document subtitle', text='<p>Document content that must stay hidden</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())

    response = client.get(reverse('activity'))
    content = response.content.decode()

    assert 'Document subtitle' in content
    assert 'Document content that must stay hidden' not in content


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
def test_finance_activity_items_can_be_marked_read_and_unread(client, activity_user):
    client.force_login(activity_user)
    asset = Asset.objects.create(code='READ', name='Read status currency', symbol='READ')
    transaction = Transaction.objects.create(asset=asset, amount=25)

    response = client.post(reverse('mark_as_read'), {'content_type': 'transaction', 'object_id': transaction.pk})

    assert response.status_code == 200
    assert response.json()['success'] is True
    read_status = ReadStatus.objects.get(user=activity_user, content_type='transaction', object_id=transaction.pk)
    assert read_status.content_type == 'transaction'
    feed_item = next(item for item in generate_feed_items(activity_user) if item['content_type'] == 'transaction' and item['object_id'] == transaction.pk)
    assert feed_item['is_read'] is True

    response = client.post(reverse('mark_unread'), {'content_type': 'transaction', 'object_id': transaction.pk})

    assert response.status_code == 200
    assert response.json()['success'] is True
    assert not ReadStatus.objects.filter(user=activity_user, content_type='transaction', object_id=transaction.pk).exists()
    feed_item = next(item for item in generate_feed_items(activity_user) if item['content_type'] == 'transaction' and item['object_id'] == transaction.pk)
    assert feed_item['is_read'] is False


@pytest.mark.django_db
def test_activity_shows_each_chat_message_as_separate_item(client, activity_user):
    client.force_login(activity_user)
    other = UserFactory(username='activity_other', email='activity_other@example.com')
    room = Room.objects.create(title='Activity test inbox', public=True)
    messages = [
        Message.objects.create(room=room, sender=other, text='Message 0\nContinuation'),
        Message.objects.create(room=room, sender=other, text='Message 1'),
        Message.objects.create(room=room, sender=other, text='Message 2'),
    ]

    response = client.get(reverse('activity'))
    content = response.content.decode()

    assert content.count('data-content-type="room_messages"') == 9
    assert all(f'data-object-id="{message.id}"' in content for message in messages)
    assert room.title in content
    assert f'Messages in {room.title}' not in content
    assert f'- <strong>{other.username}:' not in content
    assert 'Message 0 | Continuation' in content
    assert 'chat-message-count' not in content


@pytest.mark.django_db
def test_activity_group_document_keeps_document_title_separate_from_author(client, activity_user):
    client.force_login(activity_user)
    other = UserFactory(username='activity_random_member', email='activity-random@example.com')
    post = PostFactory(title='Restricted activity document', visibility=Post.Visibility.GROUP, author=activity_user)
    post.chat_room.allowed.add(other)
    message = Message.objects.create(room=post.chat_room, sender=activity_user, text='Historical welcome text', anonymous=False)

    item = next(item for item in generate_feed_items(activity_user) if item['content_type'] == 'room_messages' and item['object_id'] == message.pk)
    response = client.get(reverse('activity'))
    content = response.content.decode()

    assert item['title'] == post.title
    assert item['author'] == activity_user
    assert f'data-object-id="{message.pk}"' in content
    assert post.title in content


@pytest.mark.django_db
def test_activity_includes_public_guest_inbox_messages(client, activity_user):
    client.force_login(activity_user)
    inbox = Room.objects.get(system_key='inbox')
    message = Message.objects.create(room=inbox, sender=None, anonymous=True, text='From: Guest Name (guest@example.com)\nPlease contact me')

    response = client.get(reverse('activity'))
    content = response.content.decode()

    assert f'data-object-id="{message.pk}"' in content
    assert inbox.title in content
    assert 'Guest Name (guest@example.com)' in content
    assert 'Please contact me' in content


@pytest.mark.django_db
def test_activity_items_can_be_filtered_by_finances(client, activity_user):
    client.force_login(activity_user)
    asset = Asset.objects.create(code='ACT', name='Activity currency', symbol='ACT')
    partner = Partner.objects.create(name='Activity finance partner')
    post = PostFactory(author=activity_user, title='Excluded document', text='<p>body</p>')
    Post.objects.filter(pk=post.pk).update(updated=timezone.now())
    generate_feed_raw()
    transaction = Transaction.objects.create(asset=asset, partner=partner, amount=25)

    response = client.get(reverse('activity'), {'filtered': '1', 'type': 'transaction'})
    content = response.content.decode()

    assert f'data-object-id="{transaction.pk}"' in content
    assert partner.name in content
    assert post.title not in content
    assert 'name="type" value="transaction"' in content


@pytest.mark.django_db
def test_activity_finances_sort_and_display_by_last_modified_time(client, activity_user):
    client.force_login(activity_user)
    asset = Asset.objects.create(code='ACT', name='Activity currency', symbol='ACT')
    partner = Partner.objects.create(name='Activity finance partner')
    latest = Transaction.objects.create(asset=asset, partner=partner, amount=20)
    previous = Transaction.objects.create(asset=asset, partner=partner, amount=10)
    now = timezone.now()
    latest_update = now - timezone.timedelta(minutes=10)
    previous_update = now - timezone.timedelta(minutes=20)
    Transaction.objects.filter(pk__in=(latest.pk, previous.pk)).update(created_date=timezone.localdate() - timezone.timedelta(days=120), updated_at=previous_update)
    Transaction.objects.filter(pk=latest.pk).update(updated_at=latest_update, payment_received_date=timezone.localdate() - timezone.timedelta(days=5))
    Transaction.objects.filter(pk=previous.pk).update(payment_received_date=timezone.localdate())
    cache.delete(FEED_CACHE_KEY)

    response = client.get(reverse('activity'), {'filtered': '1', 'type': 'transaction'})
    content = response.content.decode()
    feed_items = [item for item in response.context['feed_items'] if item['content_type'] == 'transaction']

    assert [item['object_id'] for item in feed_items] == [latest.pk, previous.pk]
    assert feed_items[0]['timestamp'] == latest_update
    assert timezone.localtime(latest_update).strftime('%d.%m %H:%M') in content


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
