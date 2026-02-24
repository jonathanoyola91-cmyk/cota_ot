from django.urls import path
from .views import WorkOrdersBaseHistorialListView

urlpatterns = [
    path("", WorkOrdersBaseHistorialListView.as_view(), name="historial_workorders_base_list"),
]