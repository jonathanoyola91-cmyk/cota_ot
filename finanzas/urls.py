from django.urls import path
from . import views

app_name = "finanzas"

urlpatterns = [
    path("", views.dashboard_finanzas, name="dashboard"),
    path("<int:pk>/", views.detalle_finanzas, name="detalle"),
    path("linea/<int:linea_id>/pagar/", views.marcar_pagado, name="marcar_pagado"),
    path("aprobacion-pagos/", views.aprobacion_pagos, name="aprobacion_pagos"),
    path("aprobar-linea/<int:linea_id>/", views.aprobar_linea_pago, name="aprobar_linea_pago"),
]