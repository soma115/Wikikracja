from django.db import migrations


def _backfill_post_chat_rooms(apps, schema_editor):
    """Create chat rooms for existing documents that don't have one yet."""
    User = apps.get_model('auth', 'User')
    Post = apps.get_model('board', 'Post')
    Room = apps.get_model('chat', 'Room')

    active_users = User.objects.filter(is_active=True)
    for post in Post.objects.filter(chat_room__isnull=True).iterator():
        title = f"Document #{post.id}: {post.title}"[:90]

        # Prefer existing rooms tagged by source metadata, then by exact title.
        room = Room.objects.filter(source_app='board', source_object_id=post.id).first()
        if not room:
            room = Room.objects.filter(title=title).first()

        if not room:
            room = Room.objects.create(
                title=title,
                public=True,
                protected=True,
                founder=post.author,
                source_app='board',
                source_object_id=post.id,
            )
        else:
            if room.title != title:
                room.title = title
                room.save(update_fields=['title'])
            if room.source_app != 'board' or room.source_object_id != post.id:
                room.source_app = 'board'
                room.source_object_id = post.id
                room.save(update_fields=['source_app', 'source_object_id'])

        room.allowed.set(active_users)
        Post.objects.filter(pk=post.pk).update(chat_room=room)


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0014_post_chat_room'),
        ('chat', '0022_room_source'),
    ]

    operations = [
        migrations.RunPython(
            _backfill_post_chat_rooms,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
