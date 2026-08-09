"""Testy modeli aplikacji bookkeeping."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from bookkeeping.models import Asset, Category, Partner, Transaction

User = get_user_model()


class TransactionModelTest(TestCase):
    """Pokrycie relacji i pól modelu Transaction."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='trans_author', email='ta@example.com', password='x')
        cls.category = Category.objects.create(name='Test Cat')
        cls.partner = Partner.objects.create(name='Test Partner', email='p@example.com', phone='+48123456789', city='Warsaw', country='Poland')
        cls.asset = Asset.objects.create(code='TST', name='Test Asset', symbol='⊙')

    def test_transaction_create_with_all_relations(self):
        """Transaction trzyma wszystkie relacje (asset, category, partner, author) i poprawnie zwraca pola."""
        txn = Transaction.objects.create(type='I', asset=self.asset, category=self.category, partner=self.partner, amount=1500.50, note='Workflow test', author=self.user)

        self.assertTrue(Transaction.objects.filter(note='Workflow test').exists())
        self.assertEqual(txn.asset, self.asset)
        self.assertEqual(txn.category, self.category)
        self.assertEqual(txn.partner, self.partner)
        self.assertEqual(txn.author, self.user)
        self.assertEqual(float(txn.amount), 1500.50)
        self.assertEqual(txn.type, 'I')

    def test_asset_is_required_at_db_level(self):
        """asset=NULL musi rzucać IntegrityError. Transakcje bez aktywa po cichu
        znikały z sald (asset_balances/category_breakdown pomijają asset_id=None)."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Transaction.objects.create(type='I', asset=None, category=self.category, partner=self.partner, amount=10, author=self.user)

    def test_transaction_type_choices_contain_income_and_outgoing(self):
        """Pole type ma zdefiniowane choices 'I' (income) i 'O' (outgoing)."""
        choices = [c[0] for c in Transaction._meta.get_field('type').choices]
        self.assertIn('I', choices)
        self.assertIn('O', choices)


class AssetDefaultTests(TestCase):
    """
    Pokrycie pola Asset.is_default + classmethod Asset.get_default().

    Semantyka:
      - Tylko JEDEN asset w bazie może mieć is_default=True.
      - Zapis nowego defaulta auto-unsetuje poprzedniego (UX-friendly, brak ValidationError).
      - Asset.get_default() zwraca asset z is_default=True; fallback do pierwszego
        dodanego (najmniejsze pk) gdy żaden nie jest oznaczony.

    Uwaga: migracja 0027_data_default_assets seeduje PLN i BTC. Czyścimy je w setUp
    żeby każdy test miał deterministyczny, pusty stan startowy.
    """

    def setUp(self):
        # Cleanup PRZED testem: kasujemy najpierw transakcje (Transaction.asset ma
        # on_delete=PROTECT), potem assety. Idempotentne dla aktualnej klasy (nie tworzymy
        # transakcji), ale chroni przyszłe rozszerzenia przed ProtectedError.
        Transaction.objects.all().delete()
        Asset.objects.all().delete()
        # Self-documenting safety net: jeśli ktoś kiedyś usunie cleanup, ta asercja
        # padnie głośno i wskaże powód zamiast cicho zmieniać semantykę testów fallbacku.
        assert Asset.objects.count() == 0, "setUp musi gwarantować pustą bazę assetów"

    def test_is_default_field_exists_with_default_false(self):
        """Nowy Asset ma is_default=False bez jawnego ustawienia."""
        asset = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł')
        self.assertFalse(asset.is_default)

    def test_can_mark_asset_as_default(self):
        """Można jawnie ustawić is_default=True i wartość persistuje po save."""
        asset = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        asset.refresh_from_db()
        self.assertTrue(asset.is_default)

    def test_setting_existing_asset_as_default_unsets_previous(self):
        """
        Auto-unset: gdy zapisujemy drugi asset z is_default=True, poprzedni traci flagę.
        Po zapisie w bazie zostaje DOKŁADNIE jeden default.
        """
        pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        btc = Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿', is_default=True)

        pln.refresh_from_db()
        btc.refresh_from_db()

        self.assertFalse(pln.is_default, "Poprzedni default powinien zostać auto-odznaczony")
        self.assertTrue(btc.is_default)
        self.assertEqual(Asset.objects.filter(is_default=True).count(), 1)

    def test_updating_asset_to_default_unsets_previous(self):
        """
        Auto-unset działa też przy update (nie tylko create): zmiana istniejącego
        assetu z is_default=False na True odznacza poprzedniego defaulta.
        """
        pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        btc = Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿', is_default=False)

        btc.is_default = True
        btc.save()

        pln.refresh_from_db()
        self.assertFalse(pln.is_default)
        self.assertTrue(btc.is_default)
        self.assertEqual(Asset.objects.filter(is_default=True).count(), 1)

    def test_saving_default_asset_does_not_unset_itself(self):
        """
        Edge case: ponowny zapis tego samego defaultowego assetu (np. zmiana name)
        nie może odznaczyć samego siebie.
        """
        pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        pln.name = 'Złoty Polski'
        pln.save()

        pln.refresh_from_db()
        self.assertTrue(pln.is_default)

    def test_form_can_promote_existing_asset_to_default(self):
        """
        REGRESSION: edit istniejącego assetu i zaznaczenie is_default=True musi przejść
        walidację formularza. UniqueConstraint na poziomie bazy NIE może blokować
        ModelForm.is_valid(), bo auto-unset w save() i tak zaspokoi constraint przed
        commitem. Bug-report: /bookkeeping/asset/1/update/ "nie da się zapisać" (sesja 2026-05-25).
        """
        from bookkeeping.forms import AssetForm

        pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=False)
        Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿', is_default=True)

        form = AssetForm(data={'code': pln.code, 'name': pln.name, 'symbol': pln.symbol, 'decimal_places': pln.decimal_places, 'is_currency': True, 'is_default': True}, instance=pln)
        self.assertTrue(form.is_valid(), f"Form should validate, got errors: {form.errors.as_json()}")
        form.save()

        pln.refresh_from_db()
        self.assertTrue(pln.is_default)
        # Auto-unset: BTC stracił flagę
        self.assertEqual(Asset.objects.filter(is_default=True).count(), 1)

    def test_bypassing_save_via_queryset_update_raises_integrity_error(self):
        """
        Bezpiecznik (UniqueConstraint): QuerySet.update() omija save() i mogłoby ustawić
        wiele defaultów. Constraint na poziomie bazy musi rzucić IntegrityError zamiast
        pozwolić na cichy bug.
        """
        Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿', is_default=False)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Asset.objects.filter(code='BTC').update(is_default=True)

    def test_get_default_returns_marked_asset(self):
        """Asset.get_default() zwraca asset oznaczony jako default."""
        Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿')
        pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)

        self.assertEqual(Asset.get_default(), pln)

    def test_get_default_returns_none_when_no_assets(self):
        """Asset.get_default() zwraca None gdy baza assetów jest pusta."""
        self.assertIsNone(Asset.get_default())

    def test_get_default_returns_first_created_when_no_default_marked(self):
        """
        Fallback: gdy istnieją assety ale żaden nie ma is_default=True,
        zwracany jest pierwszy dodany (najmniejsze pk).

        Założenie: user zwykle dodaje najpierw najważniejszą walutę (np. PLN),
        a dodatkowe (BTC, EUR) później — więc kolejność dodawania = priorytet.
        """
        pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł')
        Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿')
        Asset.objects.create(code='EUR', name='Euro', symbol='€')

        self.assertEqual(Asset.get_default(), pln)

    def test_save_rolls_back_unset_when_super_save_fails(self):
        """Atomowość: jeśli super().save() rzuci PO odznaczeniu poprzedniego defaulta,
        transakcja musi się wycofać — inaczej zostajemy z ZERO defaultów w bazie."""
        default = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        new = Asset(code='BTC', name='Bitcoin', symbol='₿', is_default=True)

        with patch('django.db.models.Model.save', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                new.save()

        default.refresh_from_db()
        self.assertTrue(default.is_default)  # rollback przywrócił flagę
