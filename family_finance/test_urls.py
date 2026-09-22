from django.contrib import messages
from django.shortcuts import redirect
from django.urls import include, path


def add_business_message(request):
    messages.error(request, "MENSAJE INTERNO DE INVENTARIO")
    return redirect("family_finance:dashboard")


urlpatterns = [
    path("pruebas/mensaje-empresa/", add_business_message),
    path("accounts/", include("accounts.urls")),
    path("familia/", include("family_finance.urls")),
]
