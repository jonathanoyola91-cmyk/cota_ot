from django.contrib import admin
from .models import PlantillaEje, PuntoMedicionEje, InstrumentoMetrologico, CalibracionInstrumento, InspeccionEje, MedicionEje

class PuntoMedicionInline(admin.TabularInline):
    model = PuntoMedicionEje
    extra = 1

@admin.register(PlantillaEje)
class PlantillaEjeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_plano", "revision", "material", "activo")
    search_fields = ("nombre", "codigo_plano")
    inlines = [PuntoMedicionInline]

@admin.register(InstrumentoMetrologico)
class InstrumentoMetrologicoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "marca", "serial", "rango", "resolucion", "fecha_vencimiento", "estado", "activo")
    search_fields = ("codigo", "nombre", "marca", "modelo", "serial")

@admin.register(InspeccionEje)
class InspeccionEjeAdmin(admin.ModelAdmin):
    list_display = ("id", "paw", "plantilla", "estado", "resultado_dimensional", "dictamen", "creado_en")
    list_filter = ("estado", "resultado_dimensional", "dictamen")

admin.site.register(MedicionEje)

@admin.register(CalibracionInstrumento)
class CalibracionInstrumentoAdmin(admin.ModelAdmin):
    list_display = ("instrumento", "fecha_calibracion", "fecha_vencimiento", "laboratorio", "numero_certificado")
    search_fields = ("instrumento__codigo", "instrumento__serial", "numero_certificado")

