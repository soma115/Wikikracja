from decimal import Decimal

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ResourceListingMoveMigrationTest(TransactionTestCase):
    migrate_from = [('bookkeeping', '0033_transaction_updated_at'), ('obywatele', '0055_individual_resource_assignments')]
    migrate_to = [('bookkeeping', '0036_resourcelisting_is_closed'), ('obywatele', '0056_remove_resourceassignment_unique_resource_assignment_name_ci_and_more')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        User = self.apps.get_model(settings.AUTH_USER_MODEL)
        Uzytkownik = self.apps.get_model('obywatele', 'Uzytkownik')
        self.user = User.objects.create(username='resource-migration')
        self.profile = Uzytkownik.objects.create(uid_id=self.user.pk)
        ResourceAssignment = self.apps.get_model('obywatele', 'ResourceAssignment')
        self.assignment = ResourceAssignment.objects.create(profile_id=self.profile.pk, name='Rower', description='Do oddania', kind='give')
        self.original_values = {
            'id': self.assignment.pk,
            'profile_id': self.profile.pk,
            'name': self.assignment.name,
            'description': self.assignment.description,
            'kind': self.assignment.kind,
            'created_at': self.assignment.created_at,
            'updated_at': self.assignment.updated_at,
        }
        self.migrate(self.migrate_to)

    def applied_apps(self):
        executor = MigrationExecutor(connection)
        return executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        self.apps = self.applied_apps()

    def test_forward_move_preserves_listing_data_and_identity(self):
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        listing = ResourceListing.objects.get(pk=self.original_values['id'])

        self.assertEqual(
            {
                'id': listing.pk,
                'profile_id': listing.profile_id,
                'name': listing.name,
                'description': listing.description,
                'kind': listing.kind,
                'created_at': listing.created_at,
                'updated_at': listing.updated_at,
            },
            self.original_values,
        )
        self.assertFalse(listing.is_closed)
        with self.assertRaises(LookupError):
            self.apps.get_model('obywatele', 'ResourceAssignment')

    def test_reverse_move_restores_rows_written_after_moving(self):
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        ResourceListing.objects.filter(pk=self.original_values['id']).update(name='Rower miejski')

        self.migrate(self.migrate_from)
        ResourceAssignment = self.apps.get_model('obywatele', 'ResourceAssignment')
        self.assertEqual(ResourceAssignment.objects.get(pk=self.original_values['id']).name, 'Rower miejski')

        self.migrate(self.migrate_to)


class TransactionEntityBackfillMigrationTest(TransactionTestCase):
    migrate_from = [('bookkeeping', '0038_transaction_entity'), ('resources', '0006_copy_financial_assets')]
    migrate_to = [('bookkeeping', '0039_backfill_transaction_entity'), ('resources', '0006_copy_financial_assets')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        Asset = self.apps.get_model('bookkeeping', 'Asset')
        Category = self.apps.get_model('bookkeeping', 'Category')
        Partner = self.apps.get_model('bookkeeping', 'Partner')
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        Entity = self.apps.get_model('resources', 'Entity')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        self.asset = Asset.objects.create(code='TXN', name='Transaction unit', symbol='T', decimal_places=3, is_currency=False)
        entity = Entity.objects.create(
            entity_type='financial_asset', name=self.asset.name, code=self.asset.code, symbol=self.asset.symbol, decimal_places=self.asset.decimal_places, is_currency=self.asset.is_currency
        )
        self.reference = LegacyEntityReference.objects.create(entity_id=entity.pk, source_model='bookkeeping.Asset', source_pk=self.asset.pk)
        self.entity_pk = entity.pk
        category = Category.objects.create(name='entity-backfill-category')
        partner = Partner.objects.create(name='entity-backfill-partner')
        transaction = Transaction.objects.create(type='I', asset_id=self.asset.pk, category_id=category.pk, partner_id=partner.pk, amount=Decimal('12.50'))
        self.transaction_pk = transaction.pk
        self.migrate(self.migrate_to)

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        executor = MigrationExecutor(connection)
        self.apps = executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def test_backfill_links_each_transaction_without_changing_legacy_financial_data(self):
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        Entity = self.apps.get_model('resources', 'Entity')
        transaction = Transaction.objects.get(pk=self.transaction_pk)
        entity = Entity.objects.get(pk=self.entity_pk)

        self.assertEqual(transaction.asset_id, self.asset.pk)
        self.assertEqual(transaction.entity_id, entity.pk)
        self.assertEqual((transaction.amount, entity.entity_type, entity.code), (Decimal('12.50'), 'financial_asset', 'TXN'))

    def test_backfill_stops_when_a_transaction_asset_has_no_entity_mapping(self):
        self.migrate(self.migrate_from)
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        LegacyEntityReference.objects.filter(pk=self.reference.pk).delete()

        with self.assertRaisesRegex(RuntimeError, 'Cannot map Transaction'):
            self.migrate(self.migrate_to)

        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        transaction = Transaction.objects.get(pk=self.transaction_pk)
        self.assertIsNone(transaction.entity_id)
        self.assertEqual(transaction.asset_id, self.asset.pk)

        LegacyEntityReference.objects.create(entity_id=self.reference.entity_id, source_model='bookkeeping.Asset', source_pk=self.asset.pk)
        self.migrate(self.migrate_to)

    def test_reverse_backfill_clears_entity_fk_but_keeps_asset_fk(self):
        self.migrate(self.migrate_from)

        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        transaction = Transaction.objects.get(pk=self.transaction_pk)

        self.assertIsNone(transaction.entity_id)
        self.assertEqual(transaction.asset_id, self.asset.pk)

        self.migrate(self.migrate_to)


class FinancialEntityCutoverMigrationTest(TransactionTestCase):
    migrate_from = [('bookkeeping', '0039_backfill_transaction_entity'), ('resources', '0006_copy_financial_assets')]
    migrate_to = [('bookkeeping', '0040_transaction_entity_required_remove_asset'), ('resources', '0006_copy_financial_assets')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        Asset = self.apps.get_model('bookkeeping', 'Asset')
        Category = self.apps.get_model('bookkeeping', 'Category')
        Partner = self.apps.get_model('bookkeeping', 'Partner')
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        Entity = self.apps.get_model('resources', 'Entity')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        Transaction.objects.all().delete()
        Asset.objects.all().delete()
        Entity.objects.filter(entity_type='financial_asset').delete()
        self.asset = Asset.objects.create(code='CUT', name='Cutover unit', symbol='C', decimal_places=3, is_currency=False, is_default=True)
        entity = Entity.objects.create(
            entity_type='financial_asset',
            name=self.asset.name,
            code=self.asset.code,
            symbol=self.asset.symbol,
            decimal_places=self.asset.decimal_places,
            is_currency=self.asset.is_currency,
            is_default=self.asset.is_default,
        )
        self.entity_pk = entity.pk
        self.reference = LegacyEntityReference.objects.create(entity_id=entity.pk, source_model='bookkeeping.Asset', source_pk=self.asset.pk)
        category = Category.objects.create(name='cutover-category')
        partner = Partner.objects.create(name='cutover-partner')
        transaction = Transaction.objects.create(type='I', asset_id=self.asset.pk, entity_id=entity.pk, category_id=category.pk, partner_id=partner.pk, amount=Decimal('27.50'))
        self.transaction_pk = transaction.pk
        self.asset_pk = self.asset.pk
        self.migrate(self.migrate_to)

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        executor = MigrationExecutor(connection)
        self.apps = executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def test_forward_cutover_removes_shadow_model_and_fk_without_losing_entity_data(self):
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        Entity = self.apps.get_model('resources', 'Entity')
        transaction = Transaction.objects.get(pk=self.transaction_pk)
        entity = Entity.objects.get(pk=self.entity_pk)

        with self.assertRaises(LookupError):
            self.apps.get_model('bookkeeping', 'Asset')
        self.assertNotIn('asset', {field.name for field in Transaction._meta.get_fields()})
        self.assertFalse(Transaction._meta.get_field('entity').null)
        self.assertEqual((transaction.entity_id, transaction.amount), (entity.pk, Decimal('27.50')))
        self.assertEqual((entity.code, entity.name, entity.symbol, entity.decimal_places, entity.is_currency, entity.is_default), ('CUT', 'Cutover unit', 'C', 3, False, True))
        self.assertTrue(self.apps.get_model('resources', 'LegacyEntityReference').objects.filter(pk=self.reference.pk).exists())

    def test_cutover_aborts_on_shadow_entity_field_mismatch(self):
        self.migrate(self.migrate_from)
        Asset = self.apps.get_model('bookkeeping', 'Asset')
        Asset.objects.filter(pk=self.asset_pk).update(name='Unreviewed legacy value')

        with self.assertRaisesRegex(RuntimeError, 'mismatched fields'):
            self.migrate(self.migrate_to)

        self.apps = MigrationExecutor(connection).loader.project_state(list(MigrationExecutor(connection).loader.applied_migrations)).apps
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        Asset = self.apps.get_model('bookkeeping', 'Asset')
        self.assertTrue(Asset.objects.filter(pk=self.asset_pk).exists())
        self.assertTrue(Transaction.objects.filter(pk=self.transaction_pk, asset_id=self.asset_pk, entity_id=self.entity_pk).exists())
        Asset.objects.filter(pk=self.asset_pk).update(name='Cutover unit')

    def test_cutover_aborts_when_a_legacy_asset_has_no_entity_mapping(self):
        self.migrate(self.migrate_from)
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        LegacyEntityReference.objects.filter(pk=self.reference.pk).delete()

        with self.assertRaisesRegex(RuntimeError, 'has no financial Entity mapping'):
            self.migrate(self.migrate_to)

        self.apps = MigrationExecutor(connection).loader.project_state(list(MigrationExecutor(connection).loader.applied_migrations)).apps
        Asset = self.apps.get_model('bookkeeping', 'Asset')
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        self.assertTrue(Asset.objects.filter(pk=self.asset_pk).exists())
        self.assertTrue(Transaction.objects.filter(pk=self.transaction_pk, asset_id=self.asset_pk, entity_id=self.entity_pk).exists())
        self.reference = LegacyEntityReference.objects.create(entity_id=self.entity_pk, source_model='bookkeeping.Asset', source_pk=self.asset_pk)

    def test_cutover_aborts_on_missing_transaction_entity(self):
        self.migrate(self.migrate_from)
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        Transaction.objects.filter(pk=self.transaction_pk).update(entity_id=None)

        with self.assertRaisesRegex(RuntimeError, 'does not match mapped entity_id'):
            self.migrate(self.migrate_to)

        self.apps = MigrationExecutor(connection).loader.project_state(list(MigrationExecutor(connection).loader.applied_migrations)).apps
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        self.assertTrue(Transaction.objects.filter(pk=self.transaction_pk, asset_id=self.asset_pk, entity_id__isnull=True).exists())
        Transaction.objects.filter(pk=self.transaction_pk).update(entity_id=self.entity_pk)

    def test_reverse_cutover_restores_shadow_rows_and_transaction_fk(self):
        self.migrate(self.migrate_from)
        Asset = self.apps.get_model('bookkeeping', 'Asset')
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        asset = Asset.objects.get(pk=self.asset_pk)
        transaction = Transaction.objects.get(pk=self.transaction_pk)

        self.assertEqual((asset.code, asset.name, asset.symbol, asset.decimal_places, asset.is_currency, asset.is_default), ('CUT', 'Cutover unit', 'C', 3, False, True))
        self.assertEqual((transaction.asset_id, transaction.entity_id), (self.asset_pk, self.entity_pk))
        self.migrate(self.migrate_to)

    def test_reverse_cutover_assigns_legacy_ids_to_new_financial_entities(self):
        Entity = self.apps.get_model('resources', 'Entity')
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        Category = self.apps.get_model('bookkeeping', 'Category')
        Partner = self.apps.get_model('bookkeeping', 'Partner')
        new_entity = Entity.objects.create(entity_type='financial_asset', name='New unit', code='NEW', symbol='N')
        category = Category.objects.create(name='new-cutover-category')
        partner = Partner.objects.create(name='new-cutover-partner')
        new_transaction = Transaction.objects.create(type='I', entity_id=new_entity.pk, category_id=category.pk, partner_id=partner.pk, amount=Decimal('1.00'))

        self.migrate(self.migrate_from)
        Asset = self.apps.get_model('bookkeeping', 'Asset')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        Transaction = self.apps.get_model('bookkeeping', 'Transaction')
        reference = LegacyEntityReference.objects.get(entity_id=new_entity.pk, source_model='bookkeeping.Asset')

        self.assertTrue(Asset.objects.filter(pk=reference.source_pk, code='NEW').exists())
        self.assertEqual(Transaction.objects.get(pk=new_transaction.pk).asset_id, reference.source_pk)
        self.migrate(self.migrate_to)


class LegacyResourceEntityCutoverMigrationTest(TransactionTestCase):
    migrate_from = [
        ('bookkeeping', '0040_transaction_entity_required_remove_asset'),
        ('resources', '0007_legacyentityreference_source_profile_id'),
        ('obywatele', '0057_uzytkownik_apartment_number_uzytkownik_country_and_more'),
    ]
    migrate_to = [
        ('bookkeeping', '0041_cutover_physical_and_resource_entities'),
        ('resources', '0007_legacyentityreference_source_profile_id'),
        ('obywatele', '0057_uzytkownik_apartment_number_uzytkownik_country_and_more'),
    ]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        Entity = self.apps.get_model('resources', 'Entity')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        Country = self.apps.get_model('obywatele', 'Country')
        User = self.apps.get_model(settings.AUTH_USER_MODEL)
        Uzytkownik = self.apps.get_model('obywatele', 'Uzytkownik')

        PhysicalAsset.objects.all().delete()
        ResourceListing.objects.all().delete()
        Entity.objects.filter(entity_type__in=('physical_asset', 'resource')).delete()

        self.country, _ = Country.objects.get_or_create(code='ZZ', defaults={'name': 'Cutover test country'})
        self.user = User.objects.create(username='legacy-resource-cutover')
        self.profile = Uzytkownik.objects.create(uid_id=self.user.pk, country_id=self.country.pk, city='Test City')

        self.mapped_physical = PhysicalAsset.objects.create(name='Mapped hall', country_id=self.country.pk, city='Test City', street='Old Street', house_number='7', apartment_number='2')
        mapped_physical_entity = Entity.objects.create(
            entity_type='physical_asset',
            name=self.mapped_physical.name,
            country_id=self.mapped_physical.country_id,
            city=self.mapped_physical.city,
            street=self.mapped_physical.street,
            house_number=self.mapped_physical.house_number,
            apartment_number=self.mapped_physical.apartment_number,
        )
        self.mapped_physical_entity_id = mapped_physical_entity.pk
        LegacyEntityReference.objects.create(entity_id=mapped_physical_entity.pk, source_model='bookkeeping.PhysicalAsset', source_pk=self.mapped_physical.pk)
        self.unmapped_physical = PhysicalAsset.objects.create(name='Unmapped hall', country_id=self.country.pk, city='Other City', street='New Street')

        self.mapped_listing = ResourceListing.objects.create(profile_id=self.profile.pk, name='Mapped listing', description='Kept description', kind='borrow', is_closed=True)
        mapped_resource_entity = Entity.objects.create(
            entity_type='resource',
            name=self.mapped_listing.name,
            description=self.mapped_listing.description,
            resource_kind=self.mapped_listing.kind,
            is_closed=self.mapped_listing.is_closed,
            assigned_member_id=self.profile.pk,
        )
        Entity.objects.filter(pk=mapped_resource_entity.pk).update(created_at=self.mapped_listing.created_at, updated_at=self.mapped_listing.updated_at)
        mapped_resource_entity.refresh_from_db()
        self.assertEqual(mapped_resource_entity.created_at, self.mapped_listing.created_at)
        self.assertEqual(mapped_resource_entity.updated_at, self.mapped_listing.updated_at)
        self.mapped_listing_entity_id = mapped_resource_entity.pk
        self.mapped_listing_reference = LegacyEntityReference.objects.create(
            entity_id=mapped_resource_entity.pk, source_model='bookkeeping.ResourceListing', source_pk=self.mapped_listing.pk, source_profile_id=self.profile.pk
        )
        self.unmapped_listing = ResourceListing.objects.create(profile_id=self.profile.pk, name='Unmapped listing', description='Copied during cutover', kind='give')
        self.community_listing = ResourceListing.objects.create(profile_id=self.profile.pk, name='Shared listing', description='Community item', kind='need')
        community_entity = Entity.objects.create(
            entity_type='resource', name=self.community_listing.name, description=self.community_listing.description, resource_kind=self.community_listing.kind, is_community_owned=True
        )
        Entity.objects.filter(pk=community_entity.pk).update(created_at=self.community_listing.created_at, updated_at=self.community_listing.updated_at)
        self.community_entity_id = community_entity.pk
        LegacyEntityReference.objects.create(entity_id=community_entity.pk, source_model='bookkeeping.ResourceListing', source_pk=self.community_listing.pk, source_profile_id=self.profile.pk)
        self.assertEqual(ResourceListing.objects.count(), 3)
        self.assertEqual(LegacyEntityReference.objects.filter(source_model='bookkeeping.ResourceListing').count(), 2)
        for listing in ResourceListing.objects.all():
            reference = LegacyEntityReference.objects.filter(source_model='bookkeeping.ResourceListing', source_pk=listing.pk).first()
            if reference:
                entity = Entity.objects.get(pk=reference.entity_id)
                self.assertEqual((listing.created_at, listing.updated_at), (entity.created_at, entity.updated_at), f'legacy source pk={listing.pk}')
        self.assertEqual(LegacyEntityReference.objects.get(source_model='bookkeeping.ResourceListing', source_pk=self.mapped_listing.pk).entity_id, mapped_resource_entity.pk)
        self.assertEqual(LegacyEntityReference.objects.get(source_model='bookkeeping.ResourceListing', source_pk=self.mapped_listing.pk).entity.created_at, self.mapped_listing.created_at)

        self.migrate(self.migrate_to)

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        executor = MigrationExecutor(connection)
        self.apps = executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def test_forward_cutover_copies_missing_sources_and_preserves_community_profile_snapshot(self):
        Entity = self.apps.get_model('resources', 'Entity')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        physical_entity = Entity.objects.get(entity_type='physical_asset', name='Unmapped hall')
        resource_entity = Entity.objects.get(entity_type='resource', name='Unmapped listing')
        community_entity = Entity.objects.get(pk=self.community_entity_id)

        with self.assertRaises(LookupError):
            self.apps.get_model('bookkeeping', 'PhysicalAsset')
        with self.assertRaises(LookupError):
            self.apps.get_model('bookkeeping', 'ResourceListing')

        self.assertEqual((physical_entity.country_id, physical_entity.city, physical_entity.street), (self.country.pk, 'Other City', 'New Street'))
        self.assertIsNone(physical_entity.author_id)
        self.assertIsNone(physical_entity.assigned_member_id)
        self.assertEqual((resource_entity.description, resource_entity.resource_kind), ('Copied during cutover', 'give'))
        self.assertEqual(resource_entity.assigned_member_id, self.profile.pk)
        self.assertIsNone(resource_entity.author_id)
        self.assertTrue(community_entity.is_community_owned)
        self.assertIsNone(community_entity.assigned_member_id)
        self.assertEqual(LegacyEntityReference.objects.get(entity_id=resource_entity.pk, source_model='bookkeeping.ResourceListing').source_profile_id, self.profile.pk)

    def test_cutover_aborts_on_source_entity_mismatch_without_dropping_tables(self):
        self.migrate(self.migrate_from)
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        PhysicalAsset.objects.filter(pk=self.mapped_physical.pk).update(city='Conflicting city')

        with self.assertRaisesRegex(RuntimeError, 'mismatched Entity fields'):
            self.migrate(self.migrate_to)

        self.apps = MigrationExecutor(connection).loader.project_state(list(MigrationExecutor(connection).loader.applied_migrations)).apps
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        self.assertTrue(PhysicalAsset.objects.filter(pk=self.mapped_physical.pk).exists())
        self.assertTrue(ResourceListing.objects.filter(pk=self.mapped_listing.pk).exists())
        PhysicalAsset.objects.filter(pk=self.mapped_physical.pk).update(city='Test City')

    def test_cutover_aborts_on_legacy_resource_field_mismatch(self):
        self.migrate(self.migrate_from)
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        ResourceListing.objects.filter(pk=self.mapped_listing.pk).update(description='Conflicting description')

        with self.assertRaisesRegex(RuntimeError, 'mismatched fields'):
            self.migrate(self.migrate_to)

        self.apps = MigrationExecutor(connection).loader.project_state(list(MigrationExecutor(connection).loader.applied_migrations)).apps
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        self.assertTrue(ResourceListing.objects.filter(pk=self.mapped_listing.pk, description='Conflicting description').exists())
        ResourceListing.objects.filter(pk=self.mapped_listing.pk).update(description='Kept description')

    def test_cutover_aborts_on_orphaned_legacy_reference(self):
        self.migrate(self.migrate_from)
        Entity = self.apps.get_model('resources', 'Entity')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')
        orphan_entity = Entity.objects.create(entity_type='physical_asset', name='Orphan map item', country_id=self.country.pk, city='Test City')
        LegacyEntityReference.objects.create(entity_id=orphan_entity.pk, source_model='bookkeeping.PhysicalAsset', source_pk=999999)

        with self.assertRaisesRegex(RuntimeError, 'references have no source rows'):
            self.migrate(self.migrate_to)

        self.apps = MigrationExecutor(connection).loader.project_state(list(MigrationExecutor(connection).loader.applied_migrations)).apps
        self.assertTrue(self.apps.get_model('resources', 'Entity').objects.filter(pk=orphan_entity.pk).exists())
        self.apps.get_model('resources', 'Entity').objects.filter(pk=orphan_entity.pk).delete()

    def test_cutover_aborts_on_physical_asset_without_valid_location(self):
        self.migrate(self.migrate_from)
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        invalid_asset = PhysicalAsset.objects.create(name='No city', country_id=self.country.pk, city='')

        with self.assertRaisesRegex(RuntimeError, 'has no valid country and city'):
            self.migrate(self.migrate_to)

        self.apps = MigrationExecutor(connection).loader.project_state(list(MigrationExecutor(connection).loader.applied_migrations)).apps
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        self.assertTrue(PhysicalAsset.objects.filter(pk=invalid_asset.pk).exists())
        PhysicalAsset.objects.filter(pk=invalid_asset.pk).delete()

    def test_rollback_restores_physical_rows_resource_shadows_and_old_ids(self):
        self.migrate(self.migrate_from)
        PhysicalAsset = self.apps.get_model('bookkeeping', 'PhysicalAsset')
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        LegacyEntityReference = self.apps.get_model('resources', 'LegacyEntityReference')

        self.assertEqual(PhysicalAsset.objects.get(pk=self.unmapped_physical.pk).street, 'New Street')
        self.assertEqual(ResourceListing.objects.get(pk=self.unmapped_listing.pk).description, 'Copied during cutover')
        self.assertEqual(ResourceListing.objects.get(pk=self.community_listing.pk).profile_id, self.profile.pk)
        self.assertEqual(LegacyEntityReference.objects.get(entity_id=self.community_entity_id, source_model='bookkeeping.ResourceListing').source_profile_id, self.profile.pk)
        self.migrate(self.migrate_to)
