from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import LEGACY_FINANCIAL_ASSET_SOURCE, LEGACY_PHYSICAL_ASSET_SOURCE, LEGACY_RESOURCE_LISTING_SOURCE, Entity, LegacyEntityReference


@transaction.atomic
def sync_financial_asset_entity(asset):
    reference = LegacyEntityReference.objects.select_for_update().filter(source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=asset.pk).select_related('entity').first()
    if reference:
        entity = reference.entity
    else:
        entity = Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET, code=asset.code).first()
        if entity:
            reference = LegacyEntityReference.objects.select_for_update().filter(entity=entity, source_model=LEGACY_FINANCIAL_ASSET_SOURCE).first()
            if reference:
                reference.source_pk = asset.pk
                reference.save(update_fields=['source_pk'])
            else:
                reference = LegacyEntityReference(entity=entity, source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=asset.pk)
        else:
            entity = Entity(entity_type=Entity.Type.FINANCIAL_ASSET, code=asset.code, symbol=asset.symbol)
            reference = LegacyEntityReference(entity=entity, source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=asset.pk)

    entity.name = asset.name
    entity.code = asset.code
    entity.symbol = asset.symbol
    entity.decimal_places = asset.decimal_places
    entity.is_currency = asset.is_currency
    entity.is_default = asset.is_default
    entity.full_clean()
    entity.save()

    if reference.pk is None:
        reference.entity = entity
        reference.save()

    return entity


@transaction.atomic
def delete_financial_asset_entity(source_pk):
    reference = LegacyEntityReference.objects.select_for_update().filter(source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=source_pk).select_related('entity').first()
    if reference:
        reference.entity.delete()


def legacy_financial_asset_id_for_entity(entity):
    if entity.entity_type != Entity.Type.FINANCIAL_ASSET:
        raise ValidationError(_('Select a financial asset.'))

    source_pk = LegacyEntityReference.objects.filter(entity=entity, source_model=LEGACY_FINANCIAL_ASSET_SOURCE).values_list('source_pk', flat=True).first()
    if source_pk is None:
        raise ValidationError(_('The financial asset has no legacy record yet.'))
    return source_pk


def sync_resource_listing_entity(listing, *, author=None):
    db_alias = listing._state.db or 'default'
    with transaction.atomic(using=db_alias):
        reference = LegacyEntityReference.objects.using(db_alias).select_for_update().filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=listing.pk).select_related('entity').first()
        is_new = reference is None
        entity = reference.entity if reference else Entity(entity_type=Entity.Type.RESOURCE, author=author)
        is_new_author = author is not None and entity.author_id is None

        entity.name = listing.name
        entity.description = listing.description
        entity.assigned_member_id = listing.profile_id
        entity.is_community_owned = False
        entity.resource_kind = listing.kind
        entity.is_closed = listing.is_closed
        if is_new_author:
            entity.author = author

        if (is_new or is_new_author) and author:
            entity.full_clean()
        entity.save(using=db_alias)
        Entity.objects.using(db_alias).filter(pk=entity.pk).update(created_at=listing.created_at, updated_at=listing.updated_at)

        if is_new:
            LegacyEntityReference.objects.using(db_alias).create(entity=entity, source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=listing.pk)

    return entity


def delete_resource_listing_entity(source_pk, *, using='default'):
    with transaction.atomic(using=using):
        reference = LegacyEntityReference.objects.using(using).select_for_update().filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=source_pk).select_related('entity').first()
        if reference:
            if not reference.entity.is_community_owned:
                reference.entity.delete(using=using)


@transaction.atomic
def sync_physical_asset_entity(physical_asset, *, author=None, assignment_scope=None, assigned_member=None):
    reference = LegacyEntityReference.objects.select_for_update().filter(source_model=LEGACY_PHYSICAL_ASSET_SOURCE, source_pk=physical_asset.pk).select_related('entity').first()
    is_new_entity = reference is None
    entity = reference.entity if reference else Entity(entity_type=Entity.Type.PHYSICAL_ASSET, author=author)

    entity.name = physical_asset.name
    entity.country_id = physical_asset.country_id
    entity.city = physical_asset.city
    entity.street = physical_asset.street
    entity.house_number = physical_asset.house_number
    entity.apartment_number = physical_asset.apartment_number

    if assignment_scope == Entity.AssignmentScope.MEMBER:
        entity.is_community_owned = False
        entity.assigned_member = assigned_member
    elif assignment_scope == Entity.AssignmentScope.COMMUNITY:
        entity.is_community_owned = True
        entity.assigned_member = None

    if author and is_new_entity:
        entity.full_clean()
    elif assignment_scope and entity.author_id:
        entity.full_clean()

    entity.save()
    if is_new_entity:
        LegacyEntityReference.objects.create(entity=entity, source_model=LEGACY_PHYSICAL_ASSET_SOURCE, source_pk=physical_asset.pk)

    return entity
