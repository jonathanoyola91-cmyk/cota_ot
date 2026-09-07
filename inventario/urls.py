from django.urls import path
from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.inventario_dashboard, name="dashboard"),
    path("revision-bom/<int:pk>/", views.revision_bom_detail, name="revision_bom_detail"),
    path("revision-bom/<int:pk>/generar-entrega/", views.generar_entrega, name="generar_entrega"),
    path("recepcion/<int:pk>/", views.recepcion_detail, name="recepcion_detail"),
    path("entrega-taller/<int:pk>/", views.entrega_taller_detail, name="entrega_taller_detail"),
    path("entrega-taller/<int:pk>/pdf/", views.entrega_taller_pdf, name="entrega_taller_pdf"),
]