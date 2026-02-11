from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compras_oil/", include("compras_oil.urls")),
]
