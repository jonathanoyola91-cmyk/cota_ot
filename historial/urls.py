from django.urls import path, include

urlpatterns = [
    # Subapp: WORKORDERS BASE
    path("workorders-base/", include("historial.workorders_base.urls")),
]