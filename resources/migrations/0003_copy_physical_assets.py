from django.db import migrations


SOURCE_MODEL = 'bookkeeping.PhysicalAsset'


def copy_physical_assets(apps, schema_editor):
    alias = schema_editor.connection.alias
    PhysicalAsset = apps.get_model('bookkeeping', 'PhysicalAsset')
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')

    for asset in PhysicalAsset.objects.using(alias).order_by('pk').iterator(chunk_size=500):
        if not asset.city or not asset.city.strip():
            raise RuntimeError(f'Cannot migrate PhysicalAsset pk={asset.pk}: city is empty.')

        entity = Entity.objects.using(alias).create(
            entity_type='physical_asset',
            name=asset.name,
            country_id=asset.country_id,
            city=asset.city,
            street=asset.street,
            house_number=asset.house_number,
            apartment_number=asset.apartment_number,
        )
        LegacyEntityReference.objects.using(alias).create(
            entity_id=entity.pk,
            source_model=SOURCE_MODEL,
            source_pk=asset.pk,
        )


def remove_copied_physical_assets(apps, schema_editor):
    alias = schema_editor.connection.alias
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    entity_ids = LegacyEntityReference.objects.using(alias).filter(source_model=SOURCE_MODEL).values_list('entity_id', flat=True)
    Entity.objects.using(alias).filter(pk__in=entity_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('bookkeeping', '0037_partner_apartment_number_partner_house_number_and_more'),
        ('resources', '0002_legacyentityreference'),
    ]

    operations = [
        migrations.RunPython(copy_physical_assets, remove_copied_physical_assets),
    ]
