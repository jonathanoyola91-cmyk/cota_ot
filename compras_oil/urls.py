from django.urls import path
from .views import purchase_request_pdf, purchase_request_excel

urlpatterns = [
    path("purchase-request/<int:pk>/pdf/", purchase_request_pdf, name="purchase_request_pdf"),
    path("purchase-request/<int:pk>/excel/", purchase_request_excel, name="purchase_request_excel"),
]
