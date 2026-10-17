from django.db import migrations


SOURCE_MODEL = 'bookkeeping.Asset'


def copy_financial_assets(apps, schema_editor):
    alias = schema_editor.connection.alias
    Asset = apps.get_model('bookkeeping', 'Asset')
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')

    for asset in Asset.objects.using(alias).order_by('pk').iterator(chunk_size=500):
        entity = Entity.objects.using(alias).create(
            entity_type='financial_asset',
            name=asset.name,
            code=asset.code,
            symbol=asset.symbol,
            decimal_places=asset.decimal_places,
            is_currency=asset.is_currency,
            is_default=asset.is_default,
        )
        LegacyEntityReference.objects.using(alias).create(
            entity_id=entity.pk,
            source_model=SOURCE_MODEL,
            source_pk=asset.pk,
        )


def remove_copied_financial_assets(apps, schema_editor):
    alias = schema_editor.connection.alias
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    entity_ids = LegacyEntityReference.objects.using(alias).filter(source_model=SOURCE_MODEL).values_list('entity_id', flat=True)
    Entity.objects.using(alias).filter(pk__in=entity_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('bookkeeping', '0037_partner_apartment_number_partner_house_number_and_more'),
        ('resources', '0005_copy_resource_listings'),
    ]

    operations = [
        migrations.RunPython(copy_financial_assets, remove_copied_financial_assets),
    ]
