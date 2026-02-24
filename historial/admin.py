from django.contrib import admin
from historial.models import Historial


@admin.register(Historial)
class HistorialAdmin(admin.ModelAdmin):
    list_display = ("closed_at", "area", "title", "content_type", "object_id")
    list_filter = ("area", "content_type", "closed_at")
    search_fields = ("title", "object_id")
    ordering = ("-closed_at",)