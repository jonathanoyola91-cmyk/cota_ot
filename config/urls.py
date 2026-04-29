from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compras_oil/", include("compras_oil.urls")),
    path("quotes/", include("quotes.urls")),
    path("historial/", include("historial.urls")),

    # ✅ AGREGA ESTO:
    path("item-oil-gas/", include("item_oil_gas.urls")),
    path("", include("dashboard.urls")),
    path("paw/", include("paw_app.urls")),
    path("ot/", include("workorders.urls")),
    path("bom/", include("bom.urls")),
    path("finanzas/", include("finanzas.urls")),
    path("facturacion/", include("facturacion.urls")),
    path("inventario/", include("inventario.urls")),
]