from django.urls import path
from . import views

app_name = "campo"

urlpatterns = [
    path("", views.dashboard_campo, name="dashboard"),
    path("servicio/<int:servicio_id>/", views.detalle_servicio, name="detalle_servicio"),
    path("servicio/<int:servicio_id>/asignar-tecnicos/", views.asignar_tecnicos, name="asignar_tecnicos"),
    path("servicio/<int:servicio_id>/gasto/nuevo/", views.crear_gasto_diario, name="crear_gasto_diario"),
    path("gasto/<int:gasto_id>/editar/", views.editar_gasto_diario, name="editar_gasto_diario"),
    path("servicio/<int:servicio_id>/finalizar/", views.finalizar_servicio, name="finalizar_servicio"),
    path("servicio/<int:servicio_id>/reporte-actividades/", views.reporte_actividades, name="reporte_actividades"),
    path("servicio/<int:servicio_id>/reporte-gastos/", views.reporte_gastos, name="reporte_gastos"),
]
