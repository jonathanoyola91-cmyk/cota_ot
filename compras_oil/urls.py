from django.urls import path
from .views import purchase_request_pdf

urlpatterns = [
    path("solicitud/<int:pk>/pdf/", purchase_request_pdf, name="purchase_request_pdf"),
]
