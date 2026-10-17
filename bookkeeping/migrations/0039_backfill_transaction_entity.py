from django.db import migrations


SOURCE_MODEL = 'bookkeeping.Asset'


def _financial_entity_ids(apps, db_alias):
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    return dict(
        LegacyEntityReference.objects.using(db_alias)
        .filter(source_model=SOURCE_MODEL, entity__entity_type='financial_asset')
        .values_list('source_pk', 'entity_id')
    )


def backfill_transaction_entities(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Transaction = apps.get_model('bookkeeping', 'Transaction')
    entity_ids_by_asset = _financial_entity_ids(apps, db_alias)
    batch = []

    for transaction in Transaction.objects.using(db_alias).only('pk', 'asset_id').order_by('pk').iterator(chunk_size=500):
        entity_id = entity_ids_by_asset.get(transaction.asset_id)
        if entity_id is None:
            raise RuntimeError(f'Cannot map Transaction pk={transaction.pk} asset_id={transaction.asset_id} to a financial Entity.')

        transaction.entity_id = entity_id
        batch.append(transaction)
        if len(batch) >= 500:
            Transaction.objects.using(db_alias).bulk_update(batch, ['entity'], batch_size=500)
            batch.clear()

    if batch:
        Transaction.objects.using(db_alias).bulk_update(batch, ['entity'], batch_size=500)


def clear_backfilled_transaction_entities(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Transaction = apps.get_model('bookkeeping', 'Transaction')
    entity_ids_by_asset = _financial_entity_ids(apps, db_alias)
    batch = []

    for transaction in Transaction.objects.using(db_alias).exclude(entity_id__isnull=True).only('pk', 'asset_id', 'entity_id').order_by('pk').iterator(chunk_size=500):
        if entity_ids_by_asset.get(transaction.asset_id) != transaction.entity_id:
            continue

        transaction.entity_id = None
        batch.append(transaction)
        if len(batch) >= 500:
            Transaction.objects.using(db_alias).bulk_update(batch, ['entity'], batch_size=500)
            batch.clear()

    if batch:
        Transaction.objects.using(db_alias).bulk_update(batch, ['entity'], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ('bookkeeping', '0038_transaction_entity'),
        ('resources', '0006_copy_financial_assets'),
    ]

    operations = [
        migrations.RunPython(backfill_transaction_entities, clear_backfilled_transaction_entities),
    ]
