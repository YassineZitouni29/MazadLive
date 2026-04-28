from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def money(value):
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0.00')
    return f'{amount:,.2f} MAD'
