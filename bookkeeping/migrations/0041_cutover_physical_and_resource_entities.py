from django.db import migrations

PHYSICAL_SOURCE = 'bookkeeping.PhysicalAsset'
RESOURCE_SOURCE = 'bookkeeping.ResourceListing'
BATCH_SIZE = 500


def _reference_rows(apps, db_alias, source_model):
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    return dict(LegacyEntityReference.objects.using(db_alias).filter(source_model=source_model).values_list('source_pk', 'entity_id'))


def _check_physical_mapping(entity, source, source_pk):
    if entity.entity_type != 'physical_asset':
        raise RuntimeError(f'PhysicalAsset pk={source_pk} maps to a non-physical Entity.')
    source_fields = ('name', 'country_id', 'city', 'street', 'house_number', 'apartment_number')
    mismatches = [field for field in source_fields if getattr(source, field) != getattr(entity, field)]
    if mismatches:
        raise RuntimeError(f'PhysicalAsset pk={source_pk} has mismatched Entity fields: {mismatches}.')


def _check_resource_mapping(entity, listing, source_pk):
    if entity.entity_type != 'resource':
        raise RuntimeError(f'ResourceListing pk={source_pk} maps to a non-resource Entity.')
    source_fields = ('name', 'description', 'resource_kind', 'is_closed')
    mismatches = {
        field: (getattr(listing, 'kind' if field == 'resource_kind' else field), getattr(entity, field))
        for field in source_fields
        if getattr(listing, 'kind' if field == 'resource_kind' else field) != getattr(entity, field)
    }
    if mismatches:
        raise RuntimeError(f'ResourceListing pk={source_pk} / Entity pk={entity.pk} has mismatched fields: {list(mismatches)}.')
    if not entity.is_community_owned and entity.assigned_member_id != listing.profile_id:
        raise RuntimeError(f'ResourceListing pk={source_pk} does not match its Entity member assignment.')
    if entity.is_community_owned and entity.assigned_member_id is not None:
        raise RuntimeError(f'ResourceListing pk={source_pk} has an ambiguous community assignment.')


def copy_and_verify_legacy_entities(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    PhysicalAsset = apps.get_model('bookkeeping', 'PhysicalAsset')
    ResourceListing = apps.get_model('bookkeeping', 'ResourceListing')

    physical_references = _reference_rows(apps, db_alias, PHYSICAL_SOURCE)
    physical_rows = {
        item.pk: item for item in PhysicalAsset.objects.using(db_alias).only('pk', 'name', 'country_id', 'city', 'street', 'house_number', 'apartment_number').order_by('pk').iterator(chunk_size=BATCH_SIZE)
    }
    stale_physical_ids = set(physical_references) - set(physical_rows)
    if stale_physical_ids:
        raise RuntimeError(f'Physical asset references have no source rows: {sorted(stale_physical_ids)[:10]}')

    mapped_physical_entities = set()
    for source_pk, physical_asset in physical_rows.items():
        if not physical_asset.country_id or not (physical_asset.city or '').strip():
            raise RuntimeError(f'PhysicalAsset pk={source_pk} has no valid country and city.')
        entity_id = physical_references.get(source_pk)
        if entity_id is None:
            entity = Entity.objects.using(db_alias).create(
                entity_type='physical_asset',
                name=physical_asset.name,
                country_id=physical_asset.country_id,
                city=physical_asset.city,
                street=physical_asset.street,
                house_number=physical_asset.house_number,
                apartment_number=physical_asset.apartment_number,
            )
            LegacyEntityReference.objects.using(db_alias).create(entity_id=entity.pk, source_model=PHYSICAL_SOURCE, source_pk=source_pk)
            mapped_physical_entities.add(entity.pk)
            continue

        entity = Entity.objects.using(db_alias).get(pk=entity_id)
        _check_physical_mapping(entity, physical_asset, source_pk)
        if entity.pk in mapped_physical_entities:
            raise RuntimeError(f'Multiple PhysicalAsset rows map to Entity pk={entity.pk}.')
        mapped_physical_entities.add(entity.pk)

    resource_references = _reference_rows(apps, db_alias, RESOURCE_SOURCE)
    resource_rows = {
        listing.pk: listing
        for listing in ResourceListing.objects.using(db_alias).only('pk', 'profile_id', 'name', 'description', 'kind', 'is_closed', 'created_at', 'updated_at').order_by('pk').iterator(chunk_size=BATCH_SIZE)
    }
    stale_resource_ids = set(resource_references) - set(resource_rows)
    if stale_resource_ids:
        raise RuntimeError(f'Resource listing references have no source rows: {sorted(stale_resource_ids)[:10]}')
    resource_profile_ids = dict(LegacyEntityReference.objects.using(db_alias).filter(source_model=RESOURCE_SOURCE).values_list('source_pk', 'source_profile_id'))

    mapped_resource_entities = set()
    for source_pk, listing in resource_rows.items():
        entity_id = resource_references.get(source_pk)
        if entity_id is None:
            duplicate = (
                Entity.objects.using(db_alias).filter(entity_type='resource', resource_kind=listing.kind, name__iexact=listing.name, assigned_member_id=listing.profile_id, is_community_owned=False).exists()
            )
            if duplicate:
                raise RuntimeError(f'ResourceListing pk={source_pk} conflicts with an unmapped Entity; review the record before cutover.')
            entity = Entity.objects.using(db_alias).create(
                entity_type='resource', name=listing.name, description=listing.description, resource_kind=listing.kind, is_closed=listing.is_closed, assigned_member_id=listing.profile_id
            )
            Entity.objects.using(db_alias).filter(pk=entity.pk).update(created_at=listing.created_at, updated_at=listing.updated_at)
            LegacyEntityReference.objects.using(db_alias).create(entity_id=entity.pk, source_model=RESOURCE_SOURCE, source_pk=source_pk, source_profile_id=listing.profile_id)
            mapped_resource_entities.add(entity.pk)
            continue

        entity = Entity.objects.using(db_alias).get(pk=entity_id)
        _check_resource_mapping(entity, listing, source_pk)
        source_profile_id = resource_profile_ids.get(source_pk)
        if source_profile_id not in (None, listing.profile_id):
            raise RuntimeError(f'ResourceListing pk={source_pk} has conflicting legacy profile metadata.')
        if source_profile_id is None:
            LegacyEntityReference.objects.using(db_alias).filter(source_model=RESOURCE_SOURCE, source_pk=source_pk).update(source_profile_id=listing.profile_id)
        if entity.pk in mapped_resource_entities:
            raise RuntimeError(f'Multiple ResourceListing rows map to Entity pk={entity.pk}.')
        mapped_resource_entities.add(entity.pk)


def restore_legacy_entities(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Entity = apps.get_model('resources', 'Entity')
    LegacyEntityReference = apps.get_model('resources', 'LegacyEntityReference')
    PhysicalAsset = apps.get_model('bookkeeping', 'PhysicalAsset')
    ResourceListing = apps.get_model('bookkeeping', 'ResourceListing')
    Uzytkownik = apps.get_model('obywatele', 'Uzytkownik')

    def restore_source(source_model, entities, build_row, *, include_entity):
        references = {
            entity_id: (source_pk, source_profile_id)
            for source_pk, entity_id, source_profile_id in LegacyEntityReference.objects.using(db_alias).filter(source_model=source_model).values_list('source_pk', 'entity_id', 'source_profile_id')
        }
        next_source_pk = max((source_pk for source_pk, _ in references.values()), default=0) + 1
        rows = []
        new_references = []
        for entity in entities:
            source_pk, source_profile_id = references.get(entity.pk, (None, None))
            if source_pk is None and include_entity(entity):
                source_pk = next_source_pk
                next_source_pk += 1
                if source_model == RESOURCE_SOURCE:
                    source_profile_id = entity.assigned_member_id
                new_references.append(LegacyEntityReference(entity_id=entity.pk, source_model=source_model, source_pk=source_pk, source_profile_id=source_profile_id))
            if source_pk is None:
                continue
            row = build_row(entity, source_pk, source_profile_id)
            if row is not None:
                rows.append(row)

        LegacyEntityReference.objects.using(db_alias).bulk_create(new_references, batch_size=BATCH_SIZE)
        return rows

    physical_entities = list(Entity.objects.using(db_alias).filter(entity_type='physical_asset').select_related('country').order_by('pk'))
    physical_rows = restore_source(
        PHYSICAL_SOURCE,
        physical_entities,
        lambda entity, source_pk, source_profile_id: PhysicalAsset(
            pk=source_pk, name=entity.name, country_id=entity.country_id, city=entity.city, street=entity.street, house_number=entity.house_number, apartment_number=entity.apartment_number
        ),
        include_entity=lambda entity: True,
    )
    PhysicalAsset.objects.using(db_alias).bulk_create(physical_rows, batch_size=BATCH_SIZE)

    resource_entities = list(Entity.objects.using(db_alias).filter(entity_type='resource').order_by('pk'))

    def build_resource_listing(entity, source_pk, source_profile_id):
        profile_id = entity.assigned_member_id if not entity.is_community_owned else source_profile_id
        if profile_id is None or not Uzytkownik.objects.using(db_alias).filter(pk=profile_id).exists():
            return None
        return ResourceListing(
            pk=source_pk,
            profile_id=profile_id,
            name=entity.name,
            description=entity.description,
            kind=entity.resource_kind,
            is_closed=entity.is_closed,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    resource_rows = restore_source(RESOURCE_SOURCE, resource_entities, build_resource_listing, include_entity=lambda entity: entity.assigned_member_id is not None)
    ResourceListing.objects.using(db_alias).bulk_create(resource_rows, batch_size=BATCH_SIZE)
    ResourceListing.objects.using(db_alias).bulk_update(resource_rows, ['created_at', 'updated_at'], batch_size=BATCH_SIZE)


class Migration(migrations.Migration):
    dependencies = [
        ('bookkeeping', '0040_transaction_entity_required_remove_asset'),
        ('obywatele', '0057_uzytkownik_apartment_number_uzytkownik_country_and_more'),
        ('resources', '0007_legacyentityreference_source_profile_id'),
    ]

    operations = [migrations.RunPython(copy_and_verify_legacy_entities, restore_legacy_entities), migrations.DeleteModel(name='ResourceListing'), migrations.DeleteModel(name='PhysicalAsset')]
