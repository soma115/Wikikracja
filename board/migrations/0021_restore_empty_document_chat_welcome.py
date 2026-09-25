from django.db import migrations
from django.urls import reverse
from django.utils.html import escape


def restore_empty_document_chat_welcome(apps, schema_editor):
    Post = apps.get_model('board', 'Post')
    Message = apps.get_model('chat', 'Message')

    for post in Post.objects.filter(chat_room__isnull=False).iterator():
        room = post.chat_room
        if room.source_app != 'board' or room.source_object_id != post.pk or room.messages.exists():
            continue

        document_url = reverse('board:view_post', kwargs={'pk': post.pk})
        message_text = f"Discussion room for document: <a href='{document_url}'>{escape(post.title)}</a>"
        Message.objects.create(room=room, sender_id=post.author_id, text=message_text, anonymous=False)


class Migration(migrations.Migration):
    dependencies = [
        ('board', '0020_post_visibility'),
        ('chat', '0022_room_source'),
    ]

    operations = [
        migrations.RunPython(restore_empty_document_chat_welcome, migrations.RunPython.noop),
    ]
