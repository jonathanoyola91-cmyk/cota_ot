from django.urls import path
from . import views

app_name = "finanzas"

urlpatterns = [
    path("", views.dashboard_finanzas, name="dashboard"),
    path("gastos-fijos/", views.gastos_fijos, name="gastos_fijos"),
    path("gastos-fijos/copiar-mes/", views.copiar_gastos_mes_anterior, name="copiar_gastos_mes_anterior"),
    path("gastos-fijos/<int:pk>/editar/", views.editar_gasto_fijo, name="editar_gasto_fijo"),
    path("gastos-fijos/<int:pk>/pagar/", views.pagar_gasto_fijo, name="pagar_gasto_fijo"),
    path("inversionistas/", views.inversionistas, name="inversionistas"),
    path("inversionistas/<int:pk>/editar/", views.editar_inversionista, name="editar_inversionista"),
    path("inversionistas/<int:prestamo_id>/cuota/", views.agregar_cuota_inversionista, name="agregar_cuota_inversionista"),
    path("inversionistas/cuota/<int:pk>/pagar/", views.pagar_cuota_inversionista, name="pagar_cuota_inversionista"),
    path("proveedores-cxp/", views.cuentas_proveedores, name="cuentas_proveedores"),
    path("proveedores-cxp/<int:pk>/", views.cuenta_proveedor_detalle, name="cuenta_proveedor_detalle"),
    path("<int:pk>/", views.detalle_finanzas, name="detalle"),
    path("linea/<int:linea_id>/pagar/", views.marcar_pagado, name="marcar_pagado"),
    path("aprobacion-pagos/", views.aprobacion_pagos, name="aprobacion_pagos"),
    path("aprobar-linea/<int:linea_id>/", views.aprobar_linea_pago, name="aprobar_linea_pago"),
    path("aprobar-paw/<int:approval_id>/", views.aprobar_paw_pago, name="aprobar_paw_pago"),
    path("linea/<int:linea_id>/tipo-operacion/", views.actualizar_tipo_operacion, name="actualizar_tipo_operacion"),
]
