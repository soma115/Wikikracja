from django.db import migrations
from django.urls import reverse
from django.utils.html import escape


def convert_private_posts_to_group(apps, schema_editor):
    Post = apps.get_model('board', 'Post')
    Room = apps.get_model('chat', 'Room')
    Message = apps.get_model('chat', 'Message')
    User = apps.get_model('auth', 'User')

    active_users = User.objects.filter(is_active=True)
    for post in Post.objects.filter(visibility='private').iterator():
        room = Room.objects.filter(pk=post.chat_room_id).first() if post.chat_room_id else None
        room_title = f'Document #{post.pk}: {post.title}'[:90]
        if room is None:
            room = Room.objects.create(
                title=room_title,
                public=False,
                archived=False,
                protected=True,
                founder_id=post.author_id,
                source_app='board',
                source_object_id=post.pk,
            )
        else:
            Room.objects.filter(pk=room.pk).update(
                title=room_title,
                public=False,
                archived=False,
                protected=True,
                source_app='board',
                source_object_id=post.pk,
            )

        room.allowed.set(active_users)
        if not room.messages.exists():
            document_url = reverse('board:view_post', kwargs={'pk': post.pk})
            message_text = f"Discussion room for document: <a href='{document_url}'>{escape(post.title)}</a>"
            Message.objects.create(room=room, sender_id=post.author_id, text=message_text, anonymous=False)

        Post.objects.filter(pk=post.pk).update(visibility='group', chat_room_id=room.pk)


class Migration(migrations.Migration):
    dependencies = [
        ('board', '0021_restore_empty_document_chat_welcome'),
        ('chat', '0022_room_source'),
    ]

    operations = [
        migrations.RunPython(convert_private_posts_to_group, migrations.RunPython.noop),
    ]
