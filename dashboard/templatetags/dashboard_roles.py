from django import template

register = template.Library()


@register.simple_tag
def dashboard_roles(user):
    """Roles del sidebar disponibles en cualquier vista que herede dashboard/home.html.

    Evita depender del contexto particular de cada view. De esta forma el menú
    lateral no cambia al navegar entre PAW, BOM, Inventario, Compras, Taller, etc.
    """
    roles = {
        "es_compras": False,
        "es_finanzas": False,
        "es_gerente": False,
        "es_inventario": False,
        "es_comercial": False,
        "es_taller": False,
        "es_ingenieria": False,
        "es_campo": False,
    }

    if not user or not getattr(user, "is_authenticated", False):
        return roles

    if user.is_superuser:
        return {key: True for key in roles}

    grupos = set(user.groups.values_list("name", flat=True))

    roles.update({
        "es_compras": bool(grupos & {"COMPRAS", "COMPRAS_OIL"}),
        "es_finanzas": "FINANZAS" in grupos,
        "es_gerente": bool(grupos & {"GERENTE", "gerencia"}),
        "es_inventario": "INVENTARIO" in grupos,
        "es_comercial": bool(grupos & {"COMERCIAL", "Comercial"}),
        "es_taller": bool(grupos & {"TALLER", "Taller"}),
        "es_ingenieria": bool(grupos & {"INGENIERIA", "Ingeniería"}),
        "es_campo": "CAMPO" in grupos,
    })
    return roles
