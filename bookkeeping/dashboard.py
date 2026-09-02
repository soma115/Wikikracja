from decimal import Decimal

from .models import Asset
from .services import asset_balances


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for community finances."""
    default_asset = Asset.get_default()
    if default_asset is None:
        return {'default_asset': None, 'default_income': None, 'default_expenses': None, 'default_balance': None, 'default_symbol': None}

    balances = asset_balances(asset=default_asset)
    if balances:
        row = balances[0]
        default_income, default_expenses, default_balance = row['income'], row['expenses'], row['balance']
    else:
        default_income = default_expenses = default_balance = Decimal('0')

    return {'default_asset': default_asset, 'default_income': default_income, 'default_expenses': default_expenses, 'default_balance': default_balance, 'default_symbol': default_asset.symbol}
