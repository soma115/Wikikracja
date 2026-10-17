from django.db import migrations


def _copy_rows(source, target, db_alias):
    for row in source.objects.using(db_alias).iterator():
        target.objects.using(db_alias).create(
            pk=row.pk,
            profile_id=row.profile_id,
            name=row.name,
            description=row.description,
            kind=row.kind,
        )
        target.objects.using(db_alias).filter(pk=row.pk).update(created_at=row.created_at, updated_at=row.updated_at)


def move_resource_listings(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    ResourceAssignment = apps.get_model('obywatele', 'ResourceAssignment')
    ResourceListing = apps.get_model('bookkeeping', 'ResourceListing')
    _copy_rows(ResourceAssignment, ResourceListing, db_alias)


def restore_resource_assignments(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    ResourceListing = apps.get_model('bookkeeping', 'ResourceListing')
    ResourceAssignment = apps.get_model('obywatele', 'ResourceAssignment')
    _copy_rows(ResourceListing, ResourceAssignment, db_alias)


class Migration(migrations.Migration):
    dependencies = [
        ('bookkeeping', '0034_resourcelisting'),
        ('obywatele', '0055_individual_resource_assignments'),
    ]

    operations = [
        migrations.RunPython(move_resource_listings, restore_resource_assignments),
    ]
