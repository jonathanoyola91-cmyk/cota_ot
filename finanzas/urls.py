from django.urls import path
from . import views

app_name = "finanzas"

urlpatterns = [
    path("", views.dashboard_finanzas, name="dashboard"),
    path("proveedores-cxp/", views.cuentas_proveedores, name="cuentas_proveedores"),
    path("proveedores-cxp/<int:pk>/", views.cuenta_proveedor_detalle, name="cuenta_proveedor_detalle"),
    path("<int:pk>/", views.detalle_finanzas, name="detalle"),
    path("linea/<int:linea_id>/pagar/", views.marcar_pagado, name="marcar_pagado"),
    path("aprobacion-pagos/", views.aprobacion_pagos, name="aprobacion_pagos"),
    path("aprobar-linea/<int:linea_id>/", views.aprobar_linea_pago, name="aprobar_linea_pago"),
    path("linea/<int:linea_id>/tipo-operacion/", views.actualizar_tipo_operacion, name="actualizar_tipo_operacion"),
]
