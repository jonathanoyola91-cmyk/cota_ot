from django.urls import path
from . import views
app_name='pricing'
urlpatterns=[
 path('',views.centro_costos,name='centro_costos'),
 path('calculos/',views.lista,name='lista'),
 path('configuracion/cif/',views.configuracion_cif,name='configuracion_cif'),
 path('configuracion/cif/guardar/',views.guardar_configuracion_cif,name='guardar_configuracion_cif'),
 path('configuracion/cif/conceptos/agregar/',views.agregar_cif_item,name='agregar_cif_item'),
 path('configuracion/cif/conceptos/<int:item_id>/eliminar/',views.eliminar_cif_item,name='eliminar_cif_item'),
 path('configuracion/consumibles/',views.configuracion_consumibles,name='configuracion_consumibles'),
 path('configuracion/consumibles/guardar/',views.guardar_configuracion_consumibles,name='guardar_configuracion_consumibles'),
 path('configuracion/banco-prueba/',views.tarifa_banco,name='tarifa_banco'),
 path('configuracion/banco-prueba/guardar/',views.guardar_tarifa_banco,name='guardar_tarifa_banco'),
 path('configuracion/tarifas-mod/',views.tarifas_mod,name='tarifas_mod'),
 path('configuracion/tarifas-mod/nueva/',views.guardar_tarifa_mod,name='crear_tarifa_mod'),
 path('configuracion/tarifas-mod/<int:rate_id>/guardar/',views.guardar_tarifa_mod,name='guardar_tarifa_mod'),
 path('api/items/',views.buscar_items,name='buscar_items'),
 path('crear/',views.crear,name='crear'), path('<int:pk>/',views.detalle,name='detalle'),
 path('<int:pk>/lineas/agregar/',views.agregar_linea,name='agregar_linea'), path('<int:pk>/lineas/<int:line_id>/eliminar/',views.eliminar_linea,name='eliminar_linea'),
 path('<int:pk>/lineas/<int:line_id>/actualizar-costo/',views.actualizar_costo_linea,name='actualizar_costo_linea'),
 path('<int:pk>/costos-operativos/agregar/',views.agregar_costo_operativo,name='agregar_costo_operativo'),
 path('<int:pk>/costos-operativos/<int:cost_id>/eliminar/',views.eliminar_costo_operativo,name='eliminar_costo_operativo'),
 path('<int:pk>/actualizar/',views.actualizar_cabecera,name='actualizar_cabecera'), path('<int:pk>/publicar/',views.publicar,name='publicar')]
