"""Testy widoków CRUD aplikacji bookkeeping.

Pokrywają kontrakt, którego pilnuje deduplikacja widoków/szablonów:
toolbar w kontekście list, redirecty na listy po create/update/delete,
ochrona usuwania przez ProtectedDeleteView i własność transakcji.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from bookkeeping.models import Asset, Category, Partner, Transaction
from bookkeeping.views import AssetDeleteView

User = get_user_model()

LIST_URL_NAMES = ('bookkeeping:transaction_list', 'bookkeeping:partner_list', 'bookkeeping:category_list', 'bookkeeping:asset_list', 'bookkeeping:report_list')


class BookkeepingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='bk', email='bk@example.com', password='x')
        cls.asset = Asset.objects.create(code='TST', name='Test Asset', symbol='T')
        cls.category = Category.objects.create(name='Test Cat')
        cls.partner = Partner.objects.create(name='Test Partner')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _transaction(self, author=None):
        return Transaction.objects.create(type='I', asset=self.asset, category=self.category, partner=self.partner, amount=10, author=author or self.user)

    def test_list_views_render_with_toolbar(self):
        for url_name in LIST_URL_NAMES:
            res = self.client.get(reverse(url_name))
            self.assertEqual(res.status_code, 200, url_name)
            self.assertIn('sort_items', res.context)

    def test_views_require_login(self):
        client = Client()
        for url_name in LIST_URL_NAMES:
            self.assertEqual(client.get(reverse(url_name)).status_code, 302, url_name)

    def test_asset_create_and_update(self):
        res = self.client.post(reverse('bookkeeping:asset_create'), {'code': 'PLN2', 'name': 'Złoty', 'symbol': 'zł', 'decimal_places': 2})
        self.assertEqual(res.status_code, 302)
        asset = Asset.objects.get(code='PLN2')

        res = self.client.post(reverse('bookkeeping:asset_update', args=[asset.pk]), {'code': 'PLN2', 'name': 'Polski złoty', 'symbol': 'zł', 'decimal_places': 2})
        self.assertEqual(res.status_code, 302)
        asset.refresh_from_db()
        self.assertEqual(asset.name, 'Polski złoty')

    def test_category_and_partner_create_redirect_to_list(self):
        res = self.client.post(reverse('bookkeeping:category_create'), {'name': 'Nowa'})
        self.assertRedirects(res, reverse('bookkeeping:category_list'))
        self.assertTrue(Category.objects.filter(name='Nowa').exists())

        res = self.client.post(reverse('bookkeeping:partner_create'), {'name': 'Nowy Partner'})
        self.assertRedirects(res, reverse('bookkeeping:partner_list'))
        self.assertTrue(Partner.objects.filter(name='Nowy Partner').exists())

    def test_protected_delete_blocks_object_with_transactions(self):
        self._transaction()

        res = self.client.post(reverse('bookkeeping:asset_delete', args=[self.asset.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Asset.objects.filter(pk=self.asset.pk).exists())

        res = self.client.get(reverse('bookkeeping:asset_delete', args=[self.asset.pk]))
        self.assertTrue(res.context['has_dependencies'])
        self.assertEqual(res.context['error'], str(AssetDeleteView.protect_message))
        self.assertEqual(list(res.context['related_transactions']), list(Transaction.objects.all()))
        self.assertEqual(res.context['cancel_url'], reverse('bookkeeping:asset_list'))

    def test_protected_delete_removes_unused_object(self):
        res = self.client.post(reverse('bookkeeping:category_delete', args=[self.category.pk]))
        self.assertRedirects(res, reverse('bookkeeping:category_list'))
        self.assertFalse(Category.objects.filter(pk=self.category.pk).exists())

    def test_transaction_update_and_delete_only_by_author(self):
        other = User.objects.create_user(username='other', email='o@example.com', password='x')
        txn = self._transaction(author=other)

        res = self.client.post(reverse('bookkeeping:transaction_delete', args=[txn.pk]))
        self.assertEqual(res.status_code, 403)
        self.assertTrue(Transaction.objects.filter(pk=txn.pk).exists())

        res = self.client.get(reverse('bookkeeping:transaction_update', args=[txn.pk]))
        self.assertEqual(res.status_code, 403)

    def test_transaction_create_sets_author_and_redirects(self):
        res = self.client.post(
            reverse('bookkeeping:transaction_create'),
            {'type': 'I', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '10.5', 'payment_received_date': '2026-01-01', 'note': ''},
        )
        self.assertRedirects(res, reverse('bookkeeping:transaction_list'))
        self.assertEqual(Transaction.objects.get().author, self.user)

    def test_transaction_update_respects_next_param(self):
        txn = self._transaction()
        next_url = reverse('bookkeeping:transaction_list')
        res = self.client.post(
            reverse('bookkeeping:transaction_update', args=[txn.pk]) + f'?next={next_url}',
            {'type': 'O', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '20', 'payment_received_date': '2026-01-02', 'note': 'x'},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, next_url)
        txn.refresh_from_db()
        self.assertEqual(txn.type, 'O')
