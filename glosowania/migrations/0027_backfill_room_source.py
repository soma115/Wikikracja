from django.db import migrations


def _backfill_decyzja_room_sources(apps, schema_editor):
    """Populate source_app/source_object_id for rooms linked to decisions."""
    Room = apps.get_model('chat', 'Room')
    Decyzja = apps.get_model('glosowania', 'Decyzja')

    for decyzja in Decyzja.objects.filter(chat_room__isnull=False).iterator():
        Room.objects.filter(pk=decyzja.chat_room_id).update(
            source_app='glosowania', source_object_id=decyzja.id
        )


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0022_room_source'),
        ('glosowania', '0026_decyzja_referendum_restart_count'),
    ]

    operations = [
        migrations.RunPython(
            _backfill_decyzja_room_sources,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
