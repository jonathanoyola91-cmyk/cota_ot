# inventario/admin.py
from io import BytesIO

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import (
    InventoryReception,
    InventoryReceptionLine,
    WorkshopDelivery,
    WorkshopDeliveryLine,
)

# ======================================================
# CONFIGURACIÓN DE GRUPOS
# ======================================================

EDIT_GROUPS_INVENTARIO = {"INVENTARIO", "COMPRAS_OIL"}
EDIT_GROUPS_ENTREGA_TALLER = {"ENTREGA TALLER"}


# ======================================================
# RECEPCIÓN INVENTARIO
# ======================================================

class InventoryReceptionLineInline(admin.TabularInline):
    model = InventoryReceptionLine
    extra = 0
    can_delete = False

    fields = (
        "purchase_line",
        "cantidad_esperada",
        "cantidad_recibida",
        "fecha_llegada",
        "estado",
        "observacion_inventario",
    )

    readonly_fields = ("purchase_line", "cantidad_esperada")

    def user_can_edit(self, request):
        return (
            request.user.is_superuser
            or request.user.groups.filter(name__in=EDIT_GROUPS_INVENTARIO).exists()
        )

    def get_readonly_fields(self, request, obj=None):
        if self.user_can_edit(request):
            return self.readonly_fields
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InventoryReception)
class InventoryReceptionAdmin(admin.ModelAdmin):
    list_display = ("purchase_request", "creado_por", "actualizado_en")
    search_fields = ("purchase_request__paw_numero", "purchase_request__paw_nombre")
    inlines = [InventoryReceptionLineInline]


# ======================================================
# ENTREGA TALLER
# ======================================================

class WorkshopDeliveryLineInline(admin.TabularInline):
    model = WorkshopDeliveryLine
    extra = 0
    can_delete = False

    fields = ("codigo", "descripcion", "unidad", "cantidad_requerida", "cantidad_entregada")
    readonly_fields = ("codigo", "descripcion", "unidad", "cantidad_requerida")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkshopDelivery)
class WorkshopDeliveryAdmin(admin.ModelAdmin):
    list_display = ("paw_numero", "paw_nombre", "purchase_request", "creado_por", "actualizado_en")
    search_fields = ("purchase_request__paw_numero", "purchase_request__paw_nombre")
    autocomplete_fields = ("purchase_request",)
    inlines = [WorkshopDeliveryLineInline]

    # IMPORTANTE: aquí se activa el PDF en el dropdown de acciones
    actions = ["imprimir_entrega_taller_pdf"]

    fields = ("purchase_request", "comentarios", "creado_por", "creado_en", "actualizado_en")
    readonly_fields = ("creado_por", "creado_en", "actualizado_en")

    # ---------------- PERMISOS ----------------

    def user_can_edit(self, request):
        return (
            request.user.is_superuser
            or request.user.groups.filter(name__in=EDIT_GROUPS_ENTREGA_TALLER).exists()
        )

    def has_add_permission(self, request):
        return self.user_can_edit(request)

    def has_change_permission(self, request, obj=None):
        return self.user_can_edit(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    # ---------------- CAMPOS LISTA ----------------

    @admin.display(description="PAW")
    def paw_numero(self, obj):
        return obj.purchase_request.paw_numero or "-"

    @admin.display(description="Nombre PAW")
    def paw_nombre(self, obj):
        return obj.purchase_request.paw_nombre or "-"

    # ---------------- GUARDAR / CARGAR LÍNEAS ----------------

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.creado_por_id:
            obj.creado_por = request.user

        super().save_model(request, obj, form, change)

        pr = obj.purchase_request
        created_count = 0

        for pl in pr.lineas.all():
            _, created = WorkshopDeliveryLine.objects.get_or_create(
                delivery=obj,
                purchase_line=pl,
                defaults={
                    "codigo": pl.codigo or "",
                    "descripcion": pl.descripcion or "",
                    "unidad": pl.unidad or "",
                    "cantidad_requerida": pl.cantidad_requerida or 0,
                    # NO llenar cantidad_entregada: se diligencia manual después de imprimir
                },
            )
            if created:
                created_count += 1

        if created_count:
            messages.success(request, f"Se cargaron {created_count} línea(s) desde el PAW seleccionado.")

    # ---------------- PDF (MANUAL) ----------------

    @admin.action(description="Imprimir ENTREGA TALLER (PDF)")
    def imprimir_entrega_taller_pdf(self, request, queryset):
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        for entrega in queryset:
            pr = entrega.purchase_request
            y = height - 50

            # Encabezado
            p.setFont("Helvetica-Bold", 13)
            p.drawString(40, y, "ENTREGA TALLER")
            y -= 18

            p.setFont("Helvetica-Bold", 10)
            p.drawString(40, y, f"Paw #: {pr.paw_numero or '-'}")
            p.drawString(200, y, f"Nombre PAW: {(pr.paw_nombre or '')[:65]}")
            y -= 14

            p.setFont("Helvetica", 9)
            p.drawString(40, y, f"Fecha impresión: {timezone.localdate().isoformat()}")
            y -= 18

            p.line(40, y, 560, y)
            y -= 14

            # Header tabla
            p.setFont("Helvetica-Bold", 9)
            p.drawString(40, y, "CÓDIGO")
            p.drawString(110, y, "DESCRIPCIÓN")
            p.drawString(360, y, "UNID")
            p.drawRightString(500, y, "CANT. REQ")
            p.drawRightString(560, y, "CANT. ENT")
            y -= 12
            p.setFont("Helvetica", 9)

            # Líneas
            for ln in entrega.lineas.all():
                if y < 160:
                    p.showPage()
                    y = height - 50

                p.drawString(40, y, (ln.codigo or "")[:12])
                p.drawString(110, y, (ln.descripcion or "")[:40])
                p.drawString(360, y, (ln.unidad or "")[:8])
                p.drawRightString(500, y, f"{ln.cantidad_requerida}")

                # SIEMPRE VACÍO para diligenciar manualmente
                p.drawRightString(560, y, "")

                y -= 14

            # Comentarios (vacío)
            y -= 10
            if y < 170:
                p.showPage()
                y = height - 60

            p.setFont("Helvetica-Bold", 10)
            p.drawString(40, y, "Comentarios")
            y -= 12

            p.rect(40, y - 60, 520, 60, stroke=1, fill=0)
            y -= 85

            # Firmas
            if y < 120:
                p.showPage()
                y = height - 60

            p.setFont("Helvetica-Bold", 10)
            p.drawString(40, y, "Firmas")
            y -= 30

            p.setFont("Helvetica", 9)
            p.line(40, y, 260, y)
            p.line(330, y, 560, y)
            y -= 12
            p.drawString(40, y, "Firma entrega")
            p.drawString(330, y, "Firma recibe (Taller)")
            y -= 25

            p.line(40, y, 200, y)
            y -= 12
            p.drawString(40, y, "Fecha")

            p.showPage()

        p.save()
        buffer.seek(0)

        resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = 'attachment; filename="ENTREGA_TALLER.pdf"'
        return resp
