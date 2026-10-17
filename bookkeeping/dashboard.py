from decimal import Decimal

from .models import Asset, ResourceListing
from .services import asset_balances


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for community finances."""
    give_away_count = ResourceListing.objects.filter(kind=ResourceListing.Kind.GIVE, is_closed=False).values('profile_id').distinct().count()
    borrow_count = ResourceListing.objects.filter(kind=ResourceListing.Kind.BORROW, is_closed=False).values('profile_id').distinct().count()
    for_sale_count = ResourceListing.objects.filter(kind=ResourceListing.Kind.SALE, is_closed=False).values('profile_id').distinct().count()
    resource_counts = {'give_away_count': give_away_count, 'borrow_count': borrow_count, 'for_sale_count': for_sale_count}

    default_asset = Asset.get_default()
    if default_asset is None:
        return {'default_asset': None, 'default_income': None, 'default_expenses': None, 'default_balance': None, 'default_symbol': None, **resource_counts}

    balances = asset_balances(asset=default_asset)
    if balances:
        row = balances[0]
        default_income, default_expenses, default_balance = row['income'], row['expenses'], row['balance']
    else:
        default_income = default_expenses = default_balance = Decimal('0')

    return {'default_asset': default_asset, 'default_income': default_income, 'default_expenses': default_expenses, 'default_balance': default_balance, 'default_symbol': default_asset.symbol, **resource_counts}
