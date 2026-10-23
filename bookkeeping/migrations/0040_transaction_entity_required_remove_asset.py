import django.db.models.deletion
from django.db import migrations, models

SOURCE_MODEL = 'bookkeeping.Asset'
BATCH_SIZE = 500


def _financial_asset_references(apps, db_alias):
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    return {
        source_pk: {'entity_id': entity_id, 'entity_type': entity_type, 'code': code, 'name': name, 'symbol': symbol, 'decimal_places': decimal_places, 'is_currency': is_currency, 'is_default': is_default}
        for source_pk, entity_id, entity_type, code, name, symbol, decimal_places, is_currency, is_default in (
            LegacyEntityReference.objects.using(db_alias)
            .filter(source_model=SOURCE_MODEL)
            .values_list('source_pk', 'entity_id', 'entity__entity_type', 'entity__code', 'entity__name', 'entity__symbol', 'entity__decimal_places', 'entity__is_currency', 'entity__is_default')
        )
    }


def verify_financial_asset_cutover(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Asset = apps.get_model('bookkeeping', 'Asset')
    Transaction = apps.get_model('bookkeeping', 'Transaction')
    references = _financial_asset_references(apps, db_alias)
    legacy_assets = {asset.pk: asset for asset in Asset.objects.using(db_alias).all().only('pk', 'code', 'name', 'symbol', 'decimal_places', 'is_currency', 'is_default')}

    missing_assets = set(references) - set(legacy_assets)
    if missing_assets:
        raise RuntimeError(f'Financial asset references have no legacy rows: {sorted(missing_assets)[:10]}')

    for source_pk, asset in legacy_assets.items():
        reference = references.get(source_pk)
        if reference is None:
            raise RuntimeError(f'Cannot remove legacy Asset pk={source_pk}: it has no financial Entity mapping.')
        if reference['entity_type'] != 'financial_asset':
            raise RuntimeError(f'Cannot remove legacy Asset pk={source_pk}: its mapped Entity is not financial.')

        expected_fields = ('code', 'name', 'symbol', 'decimal_places', 'is_currency', 'is_default')
        mismatched_fields = [field for field in expected_fields if getattr(asset, field) != reference[field]]
        if mismatched_fields:
            raise RuntimeError(f'Cannot remove legacy Asset pk={source_pk}: mismatched fields {mismatched_fields}.')

    entity_id_by_asset_id = {source_pk: ref['entity_id'] for source_pk, ref in references.items()}
    for transaction in Transaction.objects.using(db_alias).only('pk', 'asset_id', 'entity_id').iterator(chunk_size=BATCH_SIZE):
        expected_entity_id = entity_id_by_asset_id.get(transaction.asset_id)
        if expected_entity_id is None:
            raise RuntimeError(f'Cannot remove Transaction.asset: transaction pk={transaction.pk} has no mapped financial Entity.')
        if transaction.entity_id != expected_entity_id:
            raise RuntimeError(f'Cannot remove Transaction.asset: transaction pk={transaction.pk} entity_id={transaction.entity_id} does not match mapped entity_id={expected_entity_id}.')


def restore_financial_assets(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Asset = apps.get_model('bookkeeping', 'Asset')
    Transaction = apps.get_model('bookkeeping', 'Transaction')
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    references = _financial_asset_references(apps, db_alias)
    source_pk_by_entity = {reference['entity_id']: source_pk for source_pk, reference in references.items()}
    next_source_pk = max(references, default=0) + 1
    assets = []
    new_references = []
    financial_entities = Entity.objects.using(db_alias).filter(entity_type='financial_asset').order_by('pk').iterator(chunk_size=BATCH_SIZE)
    for entity in financial_entities:
        source_pk = source_pk_by_entity.get(entity.pk)
        if source_pk is None:
            source_pk = next_source_pk
            next_source_pk += 1
            new_references.append(LegacyEntityReference(entity_id=entity.pk, source_model=SOURCE_MODEL, source_pk=source_pk))
        assets.append(Asset(pk=source_pk, code=entity.code, name=entity.name, symbol=entity.symbol, decimal_places=entity.decimal_places, is_currency=entity.is_currency, is_default=entity.is_default))

    Asset.objects.using(db_alias).bulk_create(assets, batch_size=BATCH_SIZE)
    LegacyEntityReference.objects.using(db_alias).bulk_create(new_references, batch_size=BATCH_SIZE)

    asset_id_by_entity_id = {reference['entity_id']: source_pk for source_pk, reference in references.items()}
    asset_id_by_entity_id.update({reference.entity_id: reference.source_pk for reference in new_references})
    transactions = Transaction.objects.using(db_alias).only('pk', 'entity_id').iterator(chunk_size=BATCH_SIZE)
    batch = []
    for transaction in transactions:
        asset_id = asset_id_by_entity_id.get(transaction.entity_id)
        if asset_id is None:
            raise RuntimeError(f'Cannot restore Transaction.asset: transaction pk={transaction.pk} entity_id={transaction.entity_id} has no legacy Asset mapping.')
        transaction.asset_id = asset_id
        batch.append(transaction)
        if len(batch) >= BATCH_SIZE:
            Transaction.objects.using(db_alias).bulk_update(batch, ['asset'], batch_size=BATCH_SIZE)
            batch.clear()
    if batch:
        Transaction.objects.using(db_alias).bulk_update(batch, ['asset'], batch_size=BATCH_SIZE)


class Migration(migrations.Migration):
    dependencies = [('bookkeeping', '0039_backfill_transaction_entity'), ('resources', '0006_copy_financial_assets')]

    operations = [
        migrations.RunPython(verify_financial_asset_cutover, migrations.RunPython.noop),
        migrations.AlterField(model_name='transaction', name='asset', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='bookkeeping.asset', verbose_name='Asset')),
        migrations.RunPython(migrations.RunPython.noop, restore_financial_assets),
        migrations.RemoveField(model_name='transaction', name='asset'),
        # Obsolete physical tables still reference Asset on some databases.
        migrations.RunSQL('DROP TABLE IF EXISTS "bookkeeping_associateasset"', reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL('DROP TABLE IF EXISTS "bookkeeping_report"', reverse_sql=migrations.RunSQL.noop),
        migrations.DeleteModel(name='Asset'),
        migrations.AlterField(
            model_name='transaction', name='entity', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookkeeping_transactions', to='resources.entity', verbose_name='Asset')
        ),
    ]
