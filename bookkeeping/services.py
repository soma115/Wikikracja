"""
Serwisy aplikacji bookkeeping — agregacje używane przez widoki, pulpit, raporty.

Single source of truth dla "ile mamy w PLN / BTC / EUR / ..." — wszystkie miejsca,
które kiedyś sumowały transakcje per asset (ReportView, pulpit, transaction_list),
docelowo wołają stąd, żeby nie powielać logiki i nie ryzykować mieszania walut.
"""

from decimal import Decimal

from django.db.models import Count, Q, Sum

from .models import Asset, Category, Transaction


def asset_balances(year=None, category=None, partner=None, asset=None):
    """
    Zwraca listę dictów per asset (jeden wpis na walutę):

        [
            {'asset': Asset(PLN), 'income': Decimal, 'expenses': Decimal,
             'balance': Decimal, 'txn_count': int},
            ...
        ]

    Reguły:
      - income = suma amount dla transakcji typu INCOMING (zawsze dodatnia)
      - expenses = suma amount dla transakcji typu OUTGOING (zawsze dodatnia)
      - balance = income - expenses (może być ujemny)
      - txn_count = liczba transakcji (I + O razem)
      - Assety bez ŻADNEJ transakcji w danym filtrze są pomijane (nie zaśmiecamy UI).
      - Sortowanie: default asset (is_default=True) pierwszy, reszta wg code alfabetycznie.

    Wszystkie parametry opcjonalne — bez nich agregujemy całą historię, wszystkie aktywa.
    Filtry łączą się AND: asset_balances(year=2026, asset=pln) → tylko 2026 + tylko PLN.
    """
    qs = Transaction.objects.all()
    if year is not None:
        qs = qs.filter(payment_received_date__year=year)
    if category is not None:
        qs = qs.filter(category=category)
    if partner is not None:
        qs = qs.filter(partner=partner)
    if asset is not None:
        qs = qs.filter(asset=asset)

    # Jedno zapytanie group-by asset, conditional sum dla I/O — żeby nie robić 2 query per asset.
    aggregated = qs.values('asset').annotate(income=Sum('amount', filter=Q(type=Transaction.INCOMING)), expenses=Sum('amount', filter=Q(type=Transaction.OUTGOING)), txn_count=Count('id'))

    # Materializujemy do dict, żeby raz pobrać Asset-y (jedno IN-query) zamiast N+1.
    by_asset_id = {row['asset']: row for row in aggregated}
    asset_objs = {a.pk: a for a in Asset.objects.filter(pk__in=by_asset_id.keys())}

    result = []
    for asset_id, row in by_asset_id.items():
        asset_obj = asset_objs.get(asset_id)
        if asset_obj is None:
            continue
        income = row['income'] or Decimal('0')
        expenses = row['expenses'] or Decimal('0')
        result.append({'asset': asset_obj, 'income': income, 'expenses': expenses, 'balance': income - expenses, 'txn_count': row['txn_count']})

    # Sort: default first, reszta alfabetycznie po code.
    result.sort(key=lambda r: (not r['asset'].is_default, r['asset'].code))
    return result


def category_breakdown(year=None):
    """
    Pivot kategorie × aktywa dla raportu /bookkeeping/report/.

    Zwraca trójkę (pivot_rows, asset_columns, asset_totals):

      pivot_rows:    [{'category_name': str, 'by_asset': {asset_id: Decimal (net)}}, ...]
                     posortowane alfabetycznie po category_name. Brakujące pary
                     (kategoria, asset) NIE pojawiają się w by_asset — template
                     renderuje '—' dla pustych komórek.
      asset_columns: [Asset, Asset, ...] — kolejność default-first, reszta wg code.
                     Tylko assety które mają jakiekolwiek transakcje w danym roku.
      asset_totals:  {asset_id: Decimal} — suma kolumny (= "Suma roku" w UI).

    Net = INCOMING - OUTGOING (może być ujemny). Kategoria NULL → '—'.

    Filtr year=None oznacza CAŁĄ historię (dla widoku "All Years Summary").
    """
    qs = Transaction.objects.all()
    if year is not None:
        qs = qs.filter(payment_received_date__year=year)

    # Agregat per (category, asset, type) — jedno query, suma per typ transakcji.
    aggregated = qs.values('category', 'asset', 'type').annotate(total=Sum('amount'))

    # net[(category_id_or_None, asset_id)] = Decimal (income - expenses)
    net = {}
    used_asset_ids = set()
    for row in aggregated:
        asset_id = row['asset']
        used_asset_ids.add(asset_id)
        key = (row['category'], asset_id)
        sign = 1 if row['type'] == Transaction.INCOMING else -1
        net[key] = net.get(key, Decimal('0')) + sign * (row['total'] or Decimal('0'))

    # Resolve obiekty: jedno IN-query na Category, jedno na Asset.
    cat_ids = {k[0] for k in net if k[0] is not None}
    cat_map = {c.id: c.name for c in Category.objects.filter(id__in=cat_ids)}
    asset_map = {a.id: a for a in Asset.objects.filter(pk__in=used_asset_ids)}

    # Asset columns: default first, reszta wg code (spójne z asset_balances).
    asset_columns = sorted(asset_map.values(), key=lambda a: (not a.is_default, a.code))

    # Buduj pivot_rows: dict per kategoria → {category_name, by_asset}
    rows_by_cat = {}
    for (cat_id, asset_id), value in net.items():
        cat_name = cat_map.get(cat_id, '—') if cat_id is not None else '—'
        row = rows_by_cat.setdefault(cat_id, {'category_name': cat_name, 'by_asset': {}})
        # Brakujące pary (zero net) pomijamy żeby template renderował '—' przez `not in`.
        # Edge case: net dokładnie 0 (income == expenses) — wtedy też pomijamy, bo
        # "0,00" i "—" niosą tę samą informację (brak salda netto).
        if value != 0:
            row['by_asset'][asset_id] = value

    # Usuń kategorie które po cleanupie nie mają ŻADNYCH wartości (wszystkie pary 0).
    pivot_rows = [r for r in rows_by_cat.values() if r['by_asset']]
    pivot_rows.sort(key=lambda r: r['category_name'])

    # Sumy kolumn — tylko z niezerowych komórek (te same które trafiły do pivot_rows).
    asset_totals = {}
    for row in pivot_rows:
        for asset_id, value in row['by_asset'].items():
            asset_totals[asset_id] = asset_totals.get(asset_id, Decimal('0')) + value

    # Asset columns ogranicz do tych z niezerowymi totals (consistency: nie pokazuj
    # kolumny w tabeli jeśli wszystkie jej komórki są puste/zerowe).
    asset_columns = [a for a in asset_columns if a.pk in asset_totals]

    return pivot_rows, asset_columns, asset_totals
