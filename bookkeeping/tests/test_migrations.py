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
