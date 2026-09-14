from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def migrate_post_visibility(apps, schema_editor):
    Post = apps.get_model('board', 'Post')
    for post in Post.objects.all().only('pk', 'is_deleted', 'is_private', 'is_public', 'system_key'):
        if post.system_key:
            visibility = 'public'
        elif post.is_deleted:
            visibility = 'archive'
        elif post.is_private:
            visibility = 'private'
        elif post.is_public:
            visibility = 'public'
        else:
            visibility = 'group'
        updates = {'visibility': visibility}
        if post.system_key:
            updates['is_important'] = True
        Post.objects.filter(pk=post.pk).update(**updates)


def reverse_post_visibility(apps, schema_editor):
    Post = apps.get_model('board', 'Post')
    for post in Post.objects.all().only('pk', 'visibility'):
        Post.objects.filter(pk=post.pk).update(
            is_deleted=post.visibility == 'archive',
            is_private=post.visibility == 'private',
            is_public=post.visibility == 'public',
        )


class Migration(migrations.Migration):
    dependencies = [
        ('board', '0019_protect_system_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='visibility',
            field=models.CharField(
                choices=[('private', _('Only me')), ('group', _('Group')), ('public', _('Public')), ('archive', _('Archive'))],
                default='group',
                max_length=10,
                verbose_name=_('Visibility'),
            ),
        ),
        migrations.RunPython(migrate_post_visibility, reverse_post_visibility),
        migrations.RemoveField(model_name='post', name='is_public'),
        migrations.RemoveField(model_name='post', name='is_private'),
        migrations.RemoveField(model_name='post', name='is_deleted'),
    ]
