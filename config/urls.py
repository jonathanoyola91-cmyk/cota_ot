from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # 👇 ESTA LÍNEA ES LA CLAVE
    path("compras_oil/", include("compras_oil.urls")),
]
