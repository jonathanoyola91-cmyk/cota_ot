from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),

    # raíz
    path("", lambda request: redirect("/dashboard/")),
    path("dashboard/", include("dashboard.urls")),

    path("accounts/", include("accounts.urls")),

    # módulos    
    path("compras/", include("compras_oil.urls")),
    path("quotes/", include("quotes.urls")),
    path("historial/", include("historial.urls")),
    path("item-oil-gas/", include("item_oil_gas.urls")),
    path("paw/", include("paw_app.urls")),
    path("ot/", include("workorders.urls")),
    path("bom/", include("bom.urls")),
    path("finanzas/", include("finanzas.urls")),
    path("facturacion/", include("facturacion.urls")),
    path("inventario/", include("inventario.urls")),
    path("taller/", include("taller.urls")),
    path("campo/", include("campo.urls")),
    
]