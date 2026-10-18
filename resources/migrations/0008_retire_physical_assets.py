from django.db import migrations, models
from django.db.models import Q


def delete_physical_assets(apps, schema_editor):
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    Transaction = apps.get_model('bookkeeping', 'Transaction')
    db_alias = schema_editor.connection.alias
    physical_entities = Entity.objects.using(db_alias).filter(entity_type='physical_asset')
    if Transaction.objects.using(db_alias).filter(entity_id__in=physical_entities.values('pk')).exists():
        raise RuntimeError('Cannot retire physical assets while transactions reference them.')
    physical_entities.delete()
    LegacyEntityReference.objects.using(db_alias).filter(source_model='bookkeeping.PhysicalAsset').delete()


class Migration(migrations.Migration):
    dependencies = [('bookkeeping', '0041_cutover_physical_and_resource_entities'), ('resources', '0007_legacyentityreference_source_profile_id')]

    operations = [
        # Retired physical-asset data is intentionally not recreated on rollback.
        migrations.RunPython(delete_physical_assets, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name='entity', name='entity_physical_location'),
        migrations.RemoveConstraint(model_name='entity', name='entity_known_type'),
        migrations.AlterField(model_name='entity', name='entity_type', field=models.CharField(choices=[('financial_asset', 'Asset'), ('resource', 'Resource')], max_length=20, verbose_name='Type')),
        migrations.AddConstraint(model_name='entity', constraint=models.CheckConstraint(condition=Q(entity_type__in=('financial_asset', 'resource')), name='entity_known_type')),
    ]
