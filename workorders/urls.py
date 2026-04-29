from django.urls import path
from . import views

urlpatterns = [
    path("", views.ot_list, name="ot_list"),
    path("<int:numero>/", views.ot_detail, name="ot_detail"),
    path("crear-desde-paw/<int:paw_id>/", views.crear_ot_desde_paw, name="crear_ot_desde_paw"),
]