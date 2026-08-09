"""Testy serwisów aplikacji bookkeeping (agregacje per asset)."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from bookkeeping.models import Asset, Category, Partner, Transaction
from bookkeeping.services import asset_balances, category_breakdown

User = get_user_model()


class AssetBalancesTests(TestCase):
    """
    Pokrycie funkcji asset_balances(year, category, partner, asset).

    Kontrakt: zwraca listę dictów per asset
      [
        {'asset': Asset, 'income': Decimal, 'expenses': Decimal,
         'balance': Decimal, 'txn_count': int},
        ...
      ]
    Sortowanie: default asset pierwszy, reszta wg code alfabetycznie.
    Assety bez transakcji są pomijane.

    Uwaga: czyścimy Transaction PRZED Asset z powodu on_delete=PROTECT.
    Migracja 0027 seeduje PLN i BTC — usuwamy żeby mieć deterministyczny stan.
    """

    def setUp(self):
        Transaction.objects.all().delete()
        Asset.objects.all().delete()
        assert Asset.objects.count() == 0, "setUp musi gwarantować pustą bazę assetów"

        self.user = User.objects.create_user(username='bob', email='b@example.com', password='x')
        self.cat_skladki = Category.objects.create(name='Składki')
        self.cat_koszty = Category.objects.create(name='Koszty')
        self.partner_a = Partner.objects.create(name='Partner A')
        self.partner_b = Partner.objects.create(name='Partner B')

        self.pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        self.btc = Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿', decimal_places=8)
        self.eur = Asset.objects.create(code='EUR', name='Euro', symbol='€')

    def _make_txn(self, asset, txn_type, amount, year=2026, category=None, partner=None):
        """Helper: tworzy transakcję z domyślnym category/partner z setUp."""
        return Transaction.objects.create(
            type=txn_type, asset=asset, amount=Decimal(str(amount)), payment_received_date=date(year, 6, 15), category=category or self.cat_skladki, partner=partner or self.partner_a, author=self.user
        )

    # ─── core behavior ────────────────────────────────────────────────

    def test_returns_empty_list_when_no_transactions(self):
        """Brak transakcji w bazie → pusta lista (nie None, nie błąd)."""
        result = asset_balances()
        self.assertEqual(result, [])

    def test_groups_transactions_by_asset(self):
        """Transakcje w PLN i BTC dają DOKŁADNIE dwa wpisy (po jednym per asset)."""
        self._make_txn(self.pln, Transaction.INCOMING, 1000)
        self._make_txn(self.pln, Transaction.INCOMING, 500)
        self._make_txn(self.btc, Transaction.INCOMING, '0.5')

        result = asset_balances()
        assets_in_result = [r['asset'] for r in result]
        self.assertEqual(len(result), 2)
        self.assertIn(self.pln, assets_in_result)
        self.assertIn(self.btc, assets_in_result)

    def test_income_and_expenses_separated_per_asset(self):
        """Dla każdego assetu: income=suma 'I', expenses=suma 'O' (dodatnia), balance=income-expenses."""
        self._make_txn(self.pln, Transaction.INCOMING, 1000)
        self._make_txn(self.pln, Transaction.OUTGOING, 300)

        result = asset_balances()
        pln_row = next(r for r in result if r['asset'] == self.pln)
        self.assertEqual(pln_row['income'], Decimal('1000'))
        self.assertEqual(pln_row['expenses'], Decimal('300'))
        self.assertEqual(pln_row['balance'], Decimal('700'))

    def test_amounts_never_mixed_between_assets(self):
        """
        REGRESSION dla głównego bugu: 1 PLN + 1 BTC NIGDY nie może dać 2 czegokolwiek.
        Każdy asset ma własne, niezależne sumy.
        """
        self._make_txn(self.pln, Transaction.INCOMING, 1)
        self._make_txn(self.btc, Transaction.INCOMING, 1)

        result = asset_balances()
        pln_row = next(r for r in result if r['asset'] == self.pln)
        btc_row = next(r for r in result if r['asset'] == self.btc)

        self.assertEqual(pln_row['income'], Decimal('1'))
        self.assertEqual(btc_row['income'], Decimal('1'))
        self.assertEqual(pln_row['balance'], Decimal('1'))
        self.assertEqual(btc_row['balance'], Decimal('1'))
        # Suma sald per asset = 2, ale to LISTA dwóch wpisów, nie jedna "2 PLN"
        self.assertEqual(len(result), 2)

    def test_negative_balance_when_expenses_exceed_income(self):
        """Wydatki > wpływy → balance ujemny (nie obcięty do zera)."""
        self._make_txn(self.pln, Transaction.INCOMING, 100)
        self._make_txn(self.pln, Transaction.OUTGOING, 250)

        result = asset_balances()
        pln_row = next(r for r in result if r['asset'] == self.pln)
        self.assertEqual(pln_row['balance'], Decimal('-150'))

    def test_assets_without_transactions_excluded(self):
        """EUR istnieje w bazie ale nie ma transakcji → nie pojawia się w wyniku."""
        self._make_txn(self.pln, Transaction.INCOMING, 100)
        # EUR i BTC bez transakcji

        result = asset_balances()
        assets_in_result = [r['asset'] for r in result]
        self.assertIn(self.pln, assets_in_result)
        self.assertNotIn(self.eur, assets_in_result)
        self.assertNotIn(self.btc, assets_in_result)

    def test_txn_count_per_asset(self):
        """txn_count liczy wszystkie transakcje (I + O) per asset."""
        self._make_txn(self.pln, Transaction.INCOMING, 100)
        self._make_txn(self.pln, Transaction.INCOMING, 200)
        self._make_txn(self.pln, Transaction.OUTGOING, 50)
        self._make_txn(self.btc, Transaction.INCOMING, '0.1')

        result = asset_balances()
        pln_row = next(r for r in result if r['asset'] == self.pln)
        btc_row = next(r for r in result if r['asset'] == self.btc)
        self.assertEqual(pln_row['txn_count'], 3)
        self.assertEqual(btc_row['txn_count'], 1)

    # ─── sorting ──────────────────────────────────────────────────────

    def test_default_asset_first_then_alphabetical(self):
        """
        Sortowanie: default asset zawsze pierwszy, reszta wg code alfabetycznie.
        PLN (default) → BTC → EUR (BTC < EUR alfabetycznie).
        """
        self._make_txn(self.pln, Transaction.INCOMING, 100)
        self._make_txn(self.btc, Transaction.INCOMING, '0.1')
        self._make_txn(self.eur, Transaction.INCOMING, 50)

        result = asset_balances()
        codes_in_order = [r['asset'].code for r in result]
        self.assertEqual(codes_in_order, ['PLN', 'BTC', 'EUR'])

    def test_no_default_asset_falls_back_to_alphabetical(self):
        """Gdy żaden asset nie jest oznaczony jako default → cała lista alfabetycznie."""
        # Odznaczamy PLN przez bezpośredni update (omija save() z auto-unset).
        Asset.objects.filter(pk=self.pln.pk).update(is_default=False)

        self._make_txn(self.pln, Transaction.INCOMING, 100)
        self._make_txn(self.btc, Transaction.INCOMING, '0.1')
        self._make_txn(self.eur, Transaction.INCOMING, 50)

        result = asset_balances()
        codes_in_order = [r['asset'].code for r in result]
        self.assertEqual(codes_in_order, ['BTC', 'EUR', 'PLN'])

    # ─── year filter ──────────────────────────────────────────────────

    def test_year_filter_includes_only_matching_year(self):
        """year=2025 → tylko transakcje z 2025, ignorując 2024 i 2026."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, year=2024)
        self._make_txn(self.pln, Transaction.INCOMING, 200, year=2025)
        self._make_txn(self.pln, Transaction.INCOMING, 300, year=2026)

        result = asset_balances(year=2025)
        pln_row = next(r for r in result if r['asset'] == self.pln)
        self.assertEqual(pln_row['income'], Decimal('200'))
        self.assertEqual(pln_row['txn_count'], 1)

    def test_year_none_aggregates_all_history(self):
        """year=None (domyślnie) → cała historia bez filtra rocznego (kluczowe dla pulpitu)."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, year=2024)
        self._make_txn(self.pln, Transaction.INCOMING, 200, year=2025)
        self._make_txn(self.pln, Transaction.INCOMING, 300, year=2026)

        result = asset_balances()
        pln_row = next(r for r in result if r['asset'] == self.pln)
        self.assertEqual(pln_row['income'], Decimal('600'))
        self.assertEqual(pln_row['txn_count'], 3)

    # ─── asset / category / partner filters ───────────────────────────

    def test_asset_filter_returns_only_that_asset(self):
        """asset=pln → wynik zawiera TYLKO PLN, nawet jeśli inne assety mają transakcje."""
        self._make_txn(self.pln, Transaction.INCOMING, 100)
        self._make_txn(self.btc, Transaction.INCOMING, '0.5')

        result = asset_balances(asset=self.pln)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['asset'], self.pln)

    def test_category_filter_limits_aggregation(self):
        """category=Składki → ignoruje transakcje z innych kategorii."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 500, category=self.cat_koszty)

        result = asset_balances(category=self.cat_skladki)
        pln_row = next(r for r in result if r['asset'] == self.pln)
        self.assertEqual(pln_row['income'], Decimal('100'))

    def test_partner_filter_limits_aggregation(self):
        """partner=Partner A → ignoruje transakcje z innymi partnerami."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, partner=self.partner_a)
        self._make_txn(self.pln, Transaction.INCOMING, 500, partner=self.partner_b)

        result = asset_balances(partner=self.partner_a)
        pln_row = next(r for r in result if r['asset'] == self.pln)
        self.assertEqual(pln_row['income'], Decimal('100'))

    def test_filters_combine_with_and_semantics(self):
        """Wiele filtrów = AND: year=2026 AND asset=pln AND category=Składki."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, year=2026, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 200, year=2025, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 300, year=2026, category=self.cat_koszty)
        self._make_txn(self.btc, Transaction.INCOMING, '0.5', year=2026, category=self.cat_skladki)

        result = asset_balances(year=2026, asset=self.pln, category=self.cat_skladki)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['asset'], self.pln)
        self.assertEqual(result[0]['income'], Decimal('100'))


class CategoryBreakdownTests(TestCase):
    """
    Pokrycie funkcji category_breakdown(year) — pivot kategorie × aktywa dla /report/.

    Kontrakt: zwraca tuple (pivot_rows, asset_columns, asset_totals)
      pivot_rows:    [{'category_name': str, 'by_asset': {asset_id: Decimal (net)}}, ...]
                     posortowane alfabetycznie po category_name; brakujące pary
                     (kategoria, asset) NIE pojawiają się w by_asset.
      asset_columns: [Asset, Asset, ...] — kolejność default-first, reszta wg code.
                     Tylko assety które mają jakiekolwiek transakcje w danym roku.
      asset_totals:  {asset_id: Decimal} — suma kolumny per asset (= "Suma roku").

    Net = income (I) - expenses (O); może być ujemny.
    Kategoria null (NULL FK) → '—' jako category_name.
    """

    def setUp(self):
        Transaction.objects.all().delete()
        Asset.objects.all().delete()
        assert Asset.objects.count() == 0, "setUp musi gwarantować pustą bazę assetów"

        self.user = User.objects.create_user(username='alice', email='a@example.com', password='x')
        self.cat_skladki = Category.objects.create(name='Składki')
        self.cat_koszty = Category.objects.create(name='Koszty operacyjne')
        self.cat_darowizny = Category.objects.create(name='Darowizny')
        self.partner = Partner.objects.create(name='Partner X')

        self.pln = Asset.objects.create(code='PLN', name='Polish Zloty', symbol='zł', is_default=True)
        self.btc = Asset.objects.create(code='BTC', name='Bitcoin', symbol='₿', decimal_places=8)
        self.eur = Asset.objects.create(code='EUR', name='Euro', symbol='€')

    def _make_txn(self, asset, txn_type, amount, year=2026, category=None):
        return Transaction.objects.create(
            type=txn_type,
            asset=asset,
            amount=Decimal(str(amount)),
            payment_received_date=date(year, 6, 15),
            category=category if category is not None else self.cat_skladki,
            partner=self.partner,
            author=self.user,
        )

    # ─── empty state ──────────────────────────────────────────────────

    def test_no_transactions_returns_empty_structures(self):
        """Brak transakcji → ([], [], {})."""
        pivot_rows, asset_columns, asset_totals = category_breakdown()
        self.assertEqual(pivot_rows, [])
        self.assertEqual(asset_columns, [])
        self.assertEqual(asset_totals, {})

    def test_year_with_no_transactions_returns_empty(self):
        """year=2099 z brakiem transakcji → ([], [], {})."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, year=2026)
        pivot_rows, asset_columns, asset_totals = category_breakdown(year=2099)
        self.assertEqual(pivot_rows, [])
        self.assertEqual(asset_columns, [])
        self.assertEqual(asset_totals, {})

    # ─── core pivot behavior ──────────────────────────────────────────

    def test_single_category_single_asset(self):
        """1 kategoria + 1 asset → 1 wiersz w pivot, 1 kolumna assetów."""
        self._make_txn(self.pln, Transaction.INCOMING, 1000, category=self.cat_skladki)

        pivot_rows, asset_columns, asset_totals = category_breakdown()
        self.assertEqual(len(pivot_rows), 1)
        self.assertEqual(pivot_rows[0]['category_name'], 'Składki')
        self.assertEqual(pivot_rows[0]['by_asset'][self.pln.pk], Decimal('1000'))
        self.assertEqual(asset_columns, [self.pln])
        self.assertEqual(asset_totals[self.pln.pk], Decimal('1000'))

    def test_pivot_groups_by_category_and_asset(self):
        """
        Pivot: 2 kategorie × 2 aktywa = 2 wiersze, każdy z 1-2 wpisami w by_asset.
        Net per (kategoria, asset) = income - expenses.
        """
        self._make_txn(self.pln, Transaction.INCOMING, 2000, category=self.cat_skladki)
        self._make_txn(self.btc, Transaction.INCOMING, '0.4', category=self.cat_darowizny)
        self._make_txn(self.pln, Transaction.OUTGOING, 500, category=self.cat_koszty)

        pivot_rows, asset_columns, asset_totals = category_breakdown()
        rows_by_cat = {r['category_name']: r['by_asset'] for r in pivot_rows}

        self.assertEqual(rows_by_cat['Składki'][self.pln.pk], Decimal('2000'))
        self.assertEqual(rows_by_cat['Darowizny'][self.btc.pk], Decimal('0.4'))
        self.assertEqual(rows_by_cat['Koszty operacyjne'][self.pln.pk], Decimal('-500'))

    def test_net_combines_income_and_expenses_within_pair(self):
        """W obrębie (kategoria, asset): income - expenses = net (jedna komórka pivot)."""
        self._make_txn(self.pln, Transaction.INCOMING, 1000, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.OUTGOING, 300, category=self.cat_skladki)

        pivot_rows, _, _ = category_breakdown()
        row = next(r for r in pivot_rows if r['category_name'] == 'Składki')
        self.assertEqual(row['by_asset'][self.pln.pk], Decimal('700'))

    def test_missing_pairs_excluded_from_by_asset(self):
        """
        Jeśli kategoria nie ma transakcji w danym assecie, klucz NIE pojawia się w by_asset.
        Template renderuje wtedy '—' dla brakujących komórek.
        """
        self._make_txn(self.pln, Transaction.INCOMING, 1000, category=self.cat_skladki)
        self._make_txn(self.btc, Transaction.INCOMING, '0.5', category=self.cat_darowizny)

        pivot_rows, _, _ = category_breakdown()
        skladki = next(r for r in pivot_rows if r['category_name'] == 'Składki')
        darowizny = next(r for r in pivot_rows if r['category_name'] == 'Darowizny')

        self.assertIn(self.pln.pk, skladki['by_asset'])
        self.assertNotIn(self.btc.pk, skladki['by_asset'])
        self.assertIn(self.btc.pk, darowizny['by_asset'])
        self.assertNotIn(self.pln.pk, darowizny['by_asset'])

    def test_null_category_renders_as_dash(self):
        """Transakcja bez kategorii (NULL) → category_name = '—'."""
        txn = self._make_txn(self.pln, Transaction.INCOMING, 500)
        Transaction.objects.filter(pk=txn.pk).update(category=None)

        pivot_rows, _, _ = category_breakdown()
        self.assertEqual(len(pivot_rows), 1)
        self.assertEqual(pivot_rows[0]['category_name'], '—')

    # ─── asset_columns ordering ───────────────────────────────────────

    def test_asset_columns_default_first_then_alphabetical(self):
        """asset_columns: default (PLN) pierwszy, reszta wg code (BTC, EUR)."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, category=self.cat_skladki)
        self._make_txn(self.btc, Transaction.INCOMING, '0.1', category=self.cat_skladki)
        self._make_txn(self.eur, Transaction.INCOMING, 50, category=self.cat_skladki)

        _, asset_columns, _ = category_breakdown()
        codes = [a.code for a in asset_columns]
        self.assertEqual(codes, ['PLN', 'BTC', 'EUR'])

    def test_asset_columns_only_for_used_assets(self):
        """Asset zdefiniowany ale bez transakcji w danym roku → nie pojawia się w kolumnach."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, category=self.cat_skladki)

        _, asset_columns, _ = category_breakdown()
        self.assertEqual(asset_columns, [self.pln])

    # ─── pivot_rows ordering ──────────────────────────────────────────

    def test_pivot_rows_alphabetical_by_category(self):
        """pivot_rows posortowane po category_name (case-sensitive jest OK, polskie znaki)."""
        self._make_txn(self.pln, Transaction.INCOMING, 1, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 1, category=self.cat_koszty)
        self._make_txn(self.pln, Transaction.INCOMING, 1, category=self.cat_darowizny)

        pivot_rows, _, _ = category_breakdown()
        names = [r['category_name'] for r in pivot_rows]
        self.assertEqual(names, sorted(names))

    # ─── asset_totals ──────────────────────────────────────────────────

    def test_asset_totals_sums_column_per_asset(self):
        """asset_totals: suma wszystkich net per asset (= 'Suma roku' w UI)."""
        self._make_txn(self.pln, Transaction.INCOMING, 1000, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 500, category=self.cat_darowizny)
        self._make_txn(self.pln, Transaction.OUTGOING, 300, category=self.cat_koszty)
        self._make_txn(self.btc, Transaction.INCOMING, '0.4', category=self.cat_darowizny)

        _, _, asset_totals = category_breakdown()
        self.assertEqual(asset_totals[self.pln.pk], Decimal('1200'))  # 1000 + 500 - 300
        self.assertEqual(asset_totals[self.btc.pk], Decimal('0.4'))

    # ─── year filter ──────────────────────────────────────────────────

    def test_year_filter_includes_only_matching_year(self):
        """year=2025 → ignoruje 2024 i 2026 dla wszystkich struktur."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, year=2024, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 200, year=2025, category=self.cat_skladki)
        self._make_txn(self.btc, Transaction.INCOMING, '0.5', year=2026, category=self.cat_skladki)

        pivot_rows, asset_columns, asset_totals = category_breakdown(year=2025)
        self.assertEqual(len(pivot_rows), 1)
        self.assertEqual(pivot_rows[0]['by_asset'][self.pln.pk], Decimal('200'))
        self.assertEqual(asset_columns, [self.pln])
        self.assertEqual(asset_totals, {self.pln.pk: Decimal('200')})

    def test_year_none_aggregates_all_history(self):
        """year=None → cała historia bez filtra."""
        self._make_txn(self.pln, Transaction.INCOMING, 100, year=2024, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 200, year=2025, category=self.cat_skladki)
        self._make_txn(self.pln, Transaction.INCOMING, 300, year=2026, category=self.cat_skladki)

        pivot_rows, _, asset_totals = category_breakdown()
        self.assertEqual(pivot_rows[0]['by_asset'][self.pln.pk], Decimal('600'))
        self.assertEqual(asset_totals[self.pln.pk], Decimal('600'))

    def test_two_deleted_categories_produce_separate_rows(self):
        """
        Regression #3: transactions whose category was deleted (FK points to gone row)
        must produce separate pivot rows — not be merged into one '—' row.

        category on_delete=CASCADE deletes transactions too, so we simulate
        'ghost' category IDs by:
        1. reserving IDs (create+delete with no transactions),
        2. creating transactions pointing to a live category,
        3. re-pointing them to the ghost IDs via update() (bypasses FK check).
        """
        # Reserve ghost IDs (no transactions point here yet)
        ghost_a = Category.objects.create(name='_ghost_a')
        ghost_b = Category.objects.create(name='_ghost_b')
        ghost_id_a, ghost_id_b = ghost_a.pk, ghost_b.pk
        ghost_a.delete()
        ghost_b.delete()

        # Create transactions against a safe category, then re-point
        txn_a = self._make_txn(self.pln, Transaction.INCOMING, 1000, category=self.cat_skladki)
        txn_b = self._make_txn(self.pln, Transaction.INCOMING, 500, category=self.cat_skladki)
        Transaction.objects.filter(pk=txn_a.pk).update(category_id=ghost_id_a)
        Transaction.objects.filter(pk=txn_b.pk).update(category_id=ghost_id_b)

        try:
            pivot_rows, _, asset_totals = category_breakdown()

            # Bug: both ghost IDs → cat_name='—' → setdefault('—') merges them → 1 row, 1500
            # Fix: key by cat_id → 2 separate rows
            self.assertEqual(len(pivot_rows), 2, "Each deleted category must produce its own pivot row")
            self.assertEqual(asset_totals[self.pln.pk], Decimal('1500'))
            by_asset_values = sorted(r['by_asset'].get(self.pln.pk) for r in pivot_rows)
            self.assertEqual(by_asset_values, [Decimal('500'), Decimal('1000')])
        finally:
            # Remove rows with invalid FKs so teardown doesn't trip FK integrity checks
            Transaction.objects.filter(pk__in=[txn_a.pk, txn_b.pk]).delete()
