from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from obywatele.models import Country
from resources.models import Entity, LegacyEntityReference
from resources.services import match_active_offers_for_needs


class EntityModelTests(TestCase):
    def test_resource_can_be_assigned_to_a_member_or_the_community(self):
        user = get_user_model().objects.create_user(username='entity-member')
        profile = user.uzytkownik

        member_entity = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Community drill', author=user, assigned_member=profile)
        community_entity = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.BORROW, name='Shared meeting room', author=user, is_community_owned=True)

        self.assertEqual(member_entity.assigned_member, profile)
        self.assertEqual(member_entity.assignment_scope, Entity.AssignmentScope.MEMBER)
        self.assertEqual(community_entity.assignment_scope, Entity.AssignmentScope.COMMUNITY)
        self.assertIsNone(community_entity.assigned_member)

    def test_entity_cannot_be_assigned_to_a_member_and_community_together(self):
        user = get_user_model().objects.create_user(username='entity-conflicting-assignment')

        with self.assertRaises(IntegrityError), transaction.atomic():
            Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Conflicting assignment', assigned_member=user.uzytkownik, is_community_owned=True)

    def test_inactive_member_cannot_be_assigned_to_a_new_entity(self):
        author = get_user_model().objects.create_user(username='entity-author')
        inactive_user = get_user_model().objects.create_user(username='entity-inactive-member', is_active=False)
        entity = Entity(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Inactive member item', author=author, assigned_member=inactive_user.uzytkownik)

        with self.assertRaises(ValidationError) as error:
            entity.full_clean()

        self.assertIn('assigned_member', error.exception.message_dict)

    def test_deleting_assigned_member_leaves_entity_unassigned(self):
        user = get_user_model().objects.create_user(username='entity-deleted-member')
        entity = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Former member item', author=user, assigned_member=user.uzytkownik)

        user.delete()
        entity.refresh_from_db()

        self.assertIsNone(entity.assigned_member_id)
        self.assertEqual(entity.assignment_scope, Entity.AssignmentScope.UNASSIGNED)

    def test_financial_asset_requires_its_financial_fields(self):
        entity = Entity(entity_type=Entity.Type.FINANCIAL_ASSET, name='Polish zloty')

        with self.assertRaises(ValidationError) as error:
            entity.full_clean()

        self.assertIn('code', error.exception.message_dict)
        self.assertIn('symbol', error.exception.message_dict)

    def test_only_one_financial_asset_can_be_default(self):
        first = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, name='Polish zloty', code='TSTA', symbol='zł', is_currency=True, is_default=True)
        second = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, name='Euro', code='TSTB', symbol='€', is_currency=True, is_default=True)

        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertEqual(Entity.get_default_financial_asset(), second)

    def test_default_financial_asset_falls_back_to_the_first_created(self):
        Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET).delete()
        first = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, name='Zulu', code='ZZZ', symbol='Z')
        Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, name='Alpha', code='AAA', symbol='A')

        self.assertEqual(Entity.get_default_financial_asset(), first)

    def test_financial_asset_codes_are_unique(self):
        Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, name='First unit', code='TOK', symbol='T')

        with self.assertRaises(IntegrityError), transaction.atomic():
            Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, name='Second unit', code='TOK', symbol='T2')

    def test_legacy_identity_is_unique_per_source_model(self):
        physical_entity = Entity.objects.create(
            entity_type=Entity.Type.PHYSICAL_ASSET, name='Legacy physical item', country=Country.objects.get_or_create(code='ZZ', defaults={'name': 'Test country'})[0], city='Test City'
        )
        resource_entity = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Legacy resource item', is_community_owned=True)
        LegacyEntityReference.objects.create(entity=physical_entity, source_model='bookkeeping.PhysicalAsset', source_pk=1)
        LegacyEntityReference.objects.create(entity=resource_entity, source_model='bookkeeping.ResourceListing', source_pk=1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LegacyEntityReference.objects.create(entity=physical_entity, source_model='bookkeeping.PhysicalAsset', source_pk=1)

    def test_resource_names_are_unique_per_member_and_kind(self):
        first_user = get_user_model().objects.create_user(username='resource-owner-first')
        second_user = get_user_model().objects.create_user(username='resource-owner-second')
        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Drill', author=first_user, assigned_member=first_user.uzytkownik)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='drill', author=first_user, assigned_member=first_user.uzytkownik)

        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Drill', author=second_user, assigned_member=second_user.uzytkownik)
        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.SALE, name='Drill', author=first_user, assigned_member=first_user.uzytkownik)

    def test_community_resource_names_are_unique_per_kind(self):
        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Shared tool', is_community_owned=True)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='shared tool', is_community_owned=True)

    def test_physical_asset_requires_a_country_and_city(self):
        entity = Entity(entity_type=Entity.Type.PHYSICAL_ASSET, name='Community hall')

        with self.assertRaises(ValidationError) as error:
            entity.full_clean()

        self.assertIn('country', error.exception.message_dict)
        self.assertIn('city', error.exception.message_dict)

    def test_user_entity_requires_author_and_assignment(self):
        entity = Entity(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Community drill')

        with self.assertRaises(ValidationError) as error:
            entity.full_clean()

        self.assertIn('author', error.exception.message_dict)
        self.assertIn('assignment_scope', error.exception.message_dict)

    def test_legacy_physical_entity_without_author_or_assignment_can_be_updated(self):
        country, _ = Country.objects.get_or_create(code='ZZ', defaults={'name': 'Test country'})
        entity = Entity.objects.create(entity_type=Entity.Type.PHYSICAL_ASSET, name='Legacy hall', country=country, city='Test City')

        entity.name = 'Updated legacy hall'
        entity.full_clean()

        self.assertIsNone(entity.author_id)
        self.assertEqual(entity.assignment_scope, Entity.AssignmentScope.UNASSIGNED)

    def test_physical_asset_requires_location_in_the_database(self):
        country, _ = Country.objects.get_or_create(code='ZZ', defaults={'name': 'Test country'})

        with self.assertRaises(IntegrityError), transaction.atomic():
            Entity.objects.create(entity_type=Entity.Type.PHYSICAL_ASSET, name='Location missing', country=country)

    def test_non_resource_entity_cannot_be_closed(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Entity.objects.create(
                entity_type=Entity.Type.PHYSICAL_ASSET, name='Closed building', country=Country.objects.get_or_create(code='ZZ', defaults={'name': 'Test country'})[0], city='Test City', is_closed=True
            )


class ResourceMatchingServiceTests(TestCase):
    def test_matches_exact_normalized_names_for_visible_active_needs_and_offers(self):
        User = get_user_model()
        need_owner = User.objects.create_user(username='matching-need-owner')
        offer_owner = User.objects.create_user(username='matching-offer-owner')
        inactive_owner = User.objects.create_user(username='matching-inactive-owner', is_active=False)
        unrelated_owner = User.objects.create_user(username='matching-unrelated-owner')

        need = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.NEED, name=' Rower   miejski ', author=need_owner, assigned_member=need_owner.uzytkownik)
        matching_offer = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='rower miejski', author=unrelated_owner, assigned_member=offer_owner.uzytkownik)
        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.BORROW, name='Rower', description='Rower miejski', author=offer_owner, assigned_member=offer_owner.uzytkownik)
        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.SALE, name='rower miejski', author=offer_owner, assigned_member=offer_owner.uzytkownik, is_closed=True)
        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='rower miejski', assigned_member=inactive_owner.uzytkownik)
        Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.NEED, name='rower miejski', author=unrelated_owner, assigned_member=unrelated_owner.uzytkownik)

        matches = match_active_offers_for_needs(need_owner, need_owner.uzytkownik)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['need'].pk, need.pk)
        self.assertEqual([offer.pk for offer in matches[0]['offers']], [matching_offer.pk])

    def test_active_community_need_and_offer_match_for_active_member(self):
        user = get_user_model().objects.create_user(username='matching-community-member')
        need = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.NEED, name='Shared winter coats', is_community_owned=True)
        offer = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Shared winter coats', is_community_owned=True)

        matches = match_active_offers_for_needs(user, user.uzytkownik)

        self.assertEqual([(item['need'].pk, [entity.pk for entity in item['offers']]) for item in matches], [(need.pk, [offer.pk])])

    def test_inactive_user_gets_no_matching_suggestions(self):
        user = get_user_model().objects.create_user(username='matching-inactive-user', is_active=False)

        self.assertEqual(match_active_offers_for_needs(user, user.uzytkownik), [])


class PhysicalAssetMigrationTests(TransactionTestCase):
    migrate_from = [('resources', '0002_legacyentityreference')]
    migrate_to = [('resources', '0003_copy_physical_assets')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        CountryModel = self.apps.get_model('obywatele', 'Country')
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        country, _ = CountryModel.objects.get_or_create(code='PL', defaults={'name': 'Poland'})
        self.asset = PhysicalAsset.objects.create(name='Migration map hall', country_id=country.pk, city='Gdańsk', street='Długa', house_number='4', apartment_number='2')
        self.old_pk = self.asset.pk
        self.migrate(self.migrate_to)

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        executor = MigrationExecutor(connection)
        self.apps = executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def test_forward_migration_copies_location_and_tracks_the_old_identity(self):
        EntityModel = self.apps.get_model('resources', 'Entity')
        LegacyReferenceModel = self.apps.get_model('resources', 'LegacyEntityReference')
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')

        entity = EntityModel.objects.get(entity_type='physical_asset')
        reference = LegacyReferenceModel.objects.get(entity_id=entity.pk)

        self.assertEqual((entity.name, entity.country_id, entity.city, entity.street, entity.house_number, entity.apartment_number), ('Migration map hall', self.asset.country_id, 'Gdańsk', 'Długa', '4', '2'))
        self.assertIsNone(entity.author_id)
        self.assertIsNone(entity.assigned_member_id)
        self.assertFalse(entity.is_community_owned)
        self.assertEqual((reference.source_model, reference.source_pk), ('bookkeeping.PhysicalAsset', self.old_pk))
        self.assertTrue(PhysicalAsset.objects.filter(pk=self.old_pk).exists())

    def test_reverse_migration_removes_only_the_copied_entity(self):
        self.migrate(self.migrate_from)

        EntityModel = self.apps.get_model('resources', 'Entity')
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        self.assertFalse(EntityModel.objects.filter(entity_type='physical_asset').exists())
        self.assertTrue(PhysicalAsset.objects.filter(pk=self.old_pk).exists())

        self.migrate(self.migrate_to)


class ResourceListingMigrationTests(TransactionTestCase):
    migrate_from = [('resources', '0004_entity_entity_res_member_kind_uq_and_more')]
    migrate_to = [('resources', '0005_copy_resource_listings')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        UserModel = self.apps.get_model(settings.AUTH_USER_MODEL)
        CountryModel = self.apps.get_model('obywatele', 'Country')
        Uzytkownik = self.apps.get_model('obywatele', 'Uzytkownik')
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        user = UserModel.objects.create(username='listing-legacy-owner')
        country, _ = CountryModel.objects.get_or_create(code='PL', defaults={'name': 'Poland'})
        profile = Uzytkownik.objects.create(uid_id=user.pk, country_id=country.pk)
        listing = ResourceListing.objects.create(profile_id=profile.pk, name='Legacy community drill', description='Still available', kind='borrow', is_closed=True)
        self.profile_id = profile.pk
        self.old_pk = listing.pk
        self.created_at = listing.created_at
        self.updated_at = listing.updated_at
        self.migrate(self.migrate_to)

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        executor = MigrationExecutor(connection)
        self.apps = executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def test_forward_migration_preserves_listing_fields_without_inventing_author(self):
        EntityModel = self.apps.get_model('resources', 'Entity')
        LegacyReferenceModel = self.apps.get_model('resources', 'LegacyEntityReference')
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        entity = EntityModel.objects.get(entity_type='resource')
        reference = LegacyReferenceModel.objects.get(entity_id=entity.pk)

        self.assertEqual(
            (entity.name, entity.description, entity.assigned_member_id, entity.resource_kind, entity.is_closed, entity.created_at, entity.updated_at),
            ('Legacy community drill', 'Still available', self.profile_id, 'borrow', True, self.created_at, self.updated_at),
        )
        self.assertIsNone(entity.author_id)
        self.assertEqual((reference.source_model, reference.source_pk), ('bookkeeping.ResourceListing', self.old_pk))
        self.assertTrue(ResourceListing.objects.filter(pk=self.old_pk).exists())

    def test_reverse_migration_removes_only_the_copied_entity(self):
        self.migrate(self.migrate_from)

        EntityModel = self.apps.get_model('resources', 'Entity')
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        self.assertFalse(EntityModel.objects.filter(entity_type='resource').exists())
        self.assertTrue(ResourceListing.objects.filter(pk=self.old_pk).exists())

        self.migrate(self.migrate_to)


class FinancialAssetMigrationTests(TransactionTestCase):
    migrate_from = [('resources', '0005_copy_resource_listings')]
    migrate_to = [('resources', '0006_copy_financial_assets')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        Asset = self.apps.get_model('bookkeeping', 'Asset')
        Category = self.apps.get_model('bookkeeping', 'Category')
        Partner = self.apps.get_model('bookkeeping', 'Partner')
        TransactionModel = self.apps.get_model('bookkeeping', 'Transaction')
        Asset.objects.update(is_default=False)
        self.asset = Asset.objects.create(code='MIG', name='Migration unit', symbol='M', decimal_places=4, is_currency=False, is_default=True)
        category = Category.objects.create(name='Migration category')
        partner = Partner.objects.create(name='Migration partner')
        self.transaction = TransactionModel.objects.create(type='I', asset_id=self.asset.pk, category_id=category.pk, partner_id=partner.pk, amount=Decimal('12.50'))
        self.asset_pk = self.asset.pk
        self.transaction_pk = self.transaction.pk
        self.migrate(self.migrate_to)

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        executor = MigrationExecutor(connection)
        self.apps = executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def test_forward_migration_copies_financial_fields_and_keeps_transaction_source(self):
        EntityModel = self.apps.get_model('resources', 'Entity')
        LegacyReferenceModel = self.apps.get_model('resources', 'LegacyEntityReference')
        Asset = self.apps.get_model('bookkeeping', 'Asset')
        TransactionModel = self.apps.get_model('bookkeeping', 'Transaction')
        entity = EntityModel.objects.get(entity_type='financial_asset', code='MIG')
        reference = LegacyReferenceModel.objects.get(entity_id=entity.pk)
        transaction = TransactionModel.objects.get(pk=self.transaction_pk)

        self.assertEqual((entity.name, entity.code, entity.symbol, entity.decimal_places, entity.is_currency, entity.is_default), ('Migration unit', 'MIG', 'M', 4, False, True))
        self.assertIsNone(entity.author_id)
        self.assertFalse(entity.is_community_owned)
        self.assertIsNone(entity.assigned_member_id)
        self.assertEqual((reference.source_model, reference.source_pk), ('bookkeeping.Asset', self.asset_pk))
        self.assertEqual(transaction.asset_id, self.asset_pk)
        self.assertEqual(transaction.amount, Decimal('12.50'))
        self.assertTrue(Asset.objects.filter(pk=self.asset_pk).exists())

    def test_reverse_migration_removes_only_the_copied_entity(self):
        self.migrate(self.migrate_from)

        EntityModel = self.apps.get_model('resources', 'Entity')
        Asset = self.apps.get_model('bookkeeping', 'Asset')
        TransactionModel = self.apps.get_model('bookkeeping', 'Transaction')
        self.assertFalse(EntityModel.objects.filter(entity_type='financial_asset', code='MIG').exists())
        self.assertTrue(Asset.objects.filter(pk=self.asset_pk).exists())
        self.assertEqual(TransactionModel.objects.get(pk=self.transaction_pk).asset_id, self.asset_pk)

        self.migrate(self.migrate_to)
