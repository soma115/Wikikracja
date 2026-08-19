from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def normalize_decimal(value):
    try:
        normalized = Decimal(value).normalize()
        return f"{normalized:f}"
    except (InvalidOperation, TypeError):
        return value


@register.filter
def get_item(dictionary, key):
    """
    Gets an item from a dictionary using the key.
    Usage: {{ dictionary|get_item:key }}
    """
    if not dictionary:
        return None
    return dictionary.get(key)
