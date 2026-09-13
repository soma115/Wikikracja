from django.db import migrations


def protect_system_category(apps, schema_editor):
    PostCategory = apps.get_model('board', 'PostCategory')
    PostCategory.objects.filter(name='System').update(is_protected=True)


def unprotect_system_category(apps, schema_editor):
    PostCategory = apps.get_model('board', 'PostCategory')
    PostCategory.objects.filter(name='System').update(is_protected=False)


class Migration(migrations.Migration):
    dependencies = [
        ('board', '0018_post_is_deleted'),
    ]

    operations = [
        migrations.RunPython(protect_system_category, unprotect_system_category),
    ]
