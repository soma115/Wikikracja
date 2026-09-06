import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_content_type(apps, schema_editor, source, target):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    content_types = ContentType.objects.db_manager(schema_editor.connection.alias)
    source_type = content_types.filter(app_label=source, model='readstatus')
    if not source_type.exists():
        return
    if content_types.filter(app_label=target, model='readstatus').exists():
        raise RuntimeError(f'Cannot move ReadStatus content type from {source} to {target}: both content types exist. Resolve the conflict without losing permission assignments before retrying.')
    source_type.update(app_label=target)
    content_types.clear_cache()


def forwards(apps, schema_editor):
    move_content_type(apps, schema_editor, 'home', 'core')


def backwards(apps, schema_editor):
    move_content_type(apps, schema_editor, 'core', 'home')


class Migration(migrations.Migration):
    initial = True

    dependencies = [('home', '0015_remove_readstatus_state'), ('contenttypes', '0002_remove_content_type_name'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ReadStatus',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        (
                            'content_type',
                            models.CharField(
                                choices=[('post', 'Post'), ('task', 'Activity'), ('event', 'Event'), ('message', 'Message'), ('decision', 'Decision'), ('citizen', 'Citizen Activity'), ('survey', 'Survey')],
                                max_length=20,
                            ),
                        ),
                        ('object_id', models.PositiveIntegerField()),
                        ('read_at', models.DateTimeField(auto_now=True)),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'home_readstatus',
                        'indexes': [models.Index(fields=['user', 'content_type'], name='readstatus_user_content_idx')],
                        'unique_together': {('user', 'content_type', 'object_id')},
                    },
                )
            ],
            database_operations=[],
        ),
        migrations.RunPython(forwards, backwards),
    ]
