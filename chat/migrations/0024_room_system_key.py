from django.db import migrations, models


def populate_system_keys(apps, schema_editor):
    Room = apps.get_model('chat', 'Room')

    Room.objects.filter(is_inbox=True).update(system_key='inbox')
    important = Room.objects.filter(title='Ważne', system_key__isnull=True).first()
    if important is not None:
        important.system_key = 'important'
        important.save(update_fields=['system_key'])


def clear_system_keys(apps, schema_editor):
    Room = apps.get_model('chat', 'Room')
    Room.objects.filter(system_key__in=['inbox', 'important']).update(system_key=None)


class Migration(migrations.Migration):
    dependencies = [
        ('chat', '0023_message_sender_display_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='system_key',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.RunPython(populate_system_keys, clear_system_keys),
    ]
