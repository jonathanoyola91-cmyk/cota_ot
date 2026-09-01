from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django import template

register = template.Library()


@register.filter
def formato_cop(value):
    """
    Formatea un valor numérico sin decimales y con punto como separador de miles.
    Ejemplo: 3369047113 -> 3.369.047.113
    """
    if value is None or value == "":
        return "0"

    try:
        numero = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return f"{int(numero):,}".replace(",", ".")
    except (InvalidOperation, ValueError, TypeError):
        return value
