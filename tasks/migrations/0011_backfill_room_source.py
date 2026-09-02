from django.db import migrations


def _backfill_task_room_sources(apps, schema_editor):
    """Populate source_app/source_object_id for rooms linked to tasks."""
    Room = apps.get_model('chat', 'Room')
    Task = apps.get_model('tasks', 'Task')

    for task in Task.objects.filter(chat_room__isnull=False).iterator():
        Room.objects.filter(pk=task.chat_room_id).update(
            source_app='tasks', source_object_id=task.id
        )


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0022_room_source'),
        ('tasks', '0010_alter_task_chat_room'),
    ]

    operations = [
        migrations.RunPython(
            _backfill_task_room_sources,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
