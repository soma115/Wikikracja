from django.db import migrations


SOURCE_MODEL = 'bookkeeping.ResourceListing'


def copy_resource_listings(apps, schema_editor):
    alias = schema_editor.connection.alias
    ResourceListing = apps.get_model('bookkeeping', 'ResourceListing')
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')

    for listing in ResourceListing.objects.using(alias).order_by('pk').iterator(chunk_size=500):
        entity = Entity.objects.using(alias).create(
            entity_type='resource',
            name=listing.name,
            description=listing.description,
            assigned_member_id=listing.profile_id,
            resource_kind=listing.kind,
            is_closed=listing.is_closed,
        )
        Entity.objects.using(alias).filter(pk=entity.pk).update(created_at=listing.created_at, updated_at=listing.updated_at)
        LegacyEntityReference.objects.using(alias).create(
            entity_id=entity.pk,
            source_model=SOURCE_MODEL,
            source_pk=listing.pk,
        )


def remove_copied_resource_listings(apps, schema_editor):
    alias = schema_editor.connection.alias
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    entity_ids = LegacyEntityReference.objects.using(alias).filter(source_model=SOURCE_MODEL).values_list('entity_id', flat=True)
    Entity.objects.using(alias).filter(pk__in=entity_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('bookkeeping', '0037_partner_apartment_number_partner_house_number_and_more'),
        ('resources', '0004_entity_entity_res_member_kind_uq_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_resource_listings, remove_copied_resource_listings),
    ]
