# inventario/admin.py
from io import BytesIO
import os

from django.contrib import admin, messages
from django.db import models
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import InventoryReception, InventoryReceptionLine


# ---------------- LINEAS DE RECEPCIÓN ----------------

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

    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(
                attrs={"rows": 1, "style": "width:220px; resize:horizontal;"}
            )
        },
    }

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields

        if request.user.groups.filter(name="INVENTARIO").exists():
            return self.readonly_fields

        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------- RECEPCIÓN INVENTARIO ----------------

@admin.register(InventoryReception)
class InventoryReceptionAdmin(admin.ModelAdmin):
    list_display = (
        "paw_numero",
        "estado_recepcion",
        "purchase_request",
        "creado_por",
        "actualizado_en",
    )

    search_fields = (
        "purchase_request__paw_numero",
        "purchase_request__paw_nombre",
        "purchase_request__bom__workorder__numero",
    )

    inlines = [InventoryReceptionLineInline]

    actions = [
        "cerrar_paw_si_listo",
        "imprimir_formato_entrega_pdf",
    ]

    # ---------------- CAMPOS CALCULADOS ----------------

    @admin.display(description="PAW")
    def paw_numero(self, obj):
        pr = getattr(obj, "purchase_request", None)
        return getattr(pr, "paw_numero", None) or "-"

    @admin.display(description="Estado")
    def estado_recepcion(self, obj):
        qs = obj.lineas.all()
        if not qs.exists():
            return "PENDIENTE"

        pendiente = InventoryReceptionLine.Estado.PENDIENTE
        return "PENDIENTE" if qs.filter(estado=pendiente).exists() else "COMPLETO"

    # ---------------- PERMISOS ----------------

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        if request.user.groups.filter(name="INVENTARIO").exists():
            return ["creado_por", "creado_en", "actualizado_en"]
        return [f.name for f in self.model._meta.fields]

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    # ---------------- ACCIÓN: CERRAR PAW ----------------

    @admin.action(description="Cerrar PAW (solo si todo está LISTO)")
    def cerrar_paw_si_listo(self, request, queryset):
        cerrados = 0
        pendiente = InventoryReceptionLine.Estado.PENDIENTE

        for rec in queryset:
            if rec.lineas.filter(estado=pendiente).exists():
                continue

            pr = rec.purchase_request
            bom = pr.bom
            wo = bom.workorder
            paw = getattr(wo, "paw", None)

            if paw:
                paw.estado_paw = "TERMINADO"
                paw.save(update_fields=["estado_paw"])

            if pr.estado != "CERRADA":
                pr.estado = "CERRADA"
                pr.save(update_fields=["estado"])

            cerrados += 1

        messages.success(
            request,
            f"Se cerraron {cerrados} PAW(s). (Solo los que estaban 100% LISTO)"
        )

    # ---------------- PDF: FORMATO ENTREGA ----------------

    @admin.action(description="Imprimir formato de entrega (PDF)")
    def imprimir_formato_entrega_pdf(self, request, queryset):
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # ---------- Helpers PDF ----------

        def draw_logo(y):
            try:
                logo_path = os.path.join(
                    settings.BASE_DIR,
                    "static",
                    "img",
                    "logo_empresa.png",
                )
                p.drawImage(
                    logo_path,
                    420,
                    y - 15,
                    width=120,
                    height=40,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass

        def draw_header(pr, y):
            draw_logo(y)

            p.setFont("Helvetica-Bold", 12)
            p.drawString(40, y, "FORMATO ENTREGA / RECEPCIÓN - INVENTARIO")
            y -= 18

            p.setFont("Helvetica-Bold", 10)
            p.drawString(40, y, f"Paw #: {pr.paw_numero or '-'}")
            p.drawString(200, y, f"PAW Nombre: {(pr.paw_nombre or '')[:60]}")
            y -= 14

            p.setFont("Helvetica", 9)
            p.drawString(40, y, f"Fecha impresión: {timezone.localdate().isoformat()}")
            y -= 18
            return y

        def draw_table_header(y):
            p.setFont("Helvetica-Bold", 9)
            p.drawString(40, y, "LÍNEA")
            p.drawRightString(380, y, "CANT. ESPERADA")
            p.drawString(400, y, "ESTADO")
            p.drawRightString(560, y, "CANT. ENTREGADA")
            y -= 10
            p.line(40, y, 560, y)
            y -= 12
            p.setFont("Helvetica", 9)
            return y

        def draw_signatures(y):
            if y < 140:
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
            p.drawString(330, y, "Firma recibe")
            y -= 25

            p.line(40, y, 200, y)
            y -= 12
            p.drawString(40, y, "Fecha")
            return y

        # ---------- Generación ----------

        y = height - 50
        first_paw = None
        count = 0

        qs = queryset.select_related("purchase_request").prefetch_related("lineas__purchase_line")

        for rec in qs:
            pr = rec.purchase_request
            count += 1
            if not first_paw:
                first_paw = pr.paw_numero or str(pr.id)

            if count > 1:
                p.showPage()
                y = height - 50

            y = draw_header(pr, y)
            y = draw_table_header(y)

            for ln in rec.lineas.select_related("purchase_line").all():
                if y < 170:
                    p.showPage()
                    y = height - 50
                    y = draw_header(pr, y)
                    y = draw_table_header(y)

                pl = ln.purchase_line
                texto = f"{pl.codigo or ''} - {pl.descripcion or ''}"[:55]

                p.drawString(40, y, texto)
                p.drawRightString(380, y, f"{ln.cantidad_esperada}")
                p.drawString(400, y, ln.estado)
                p.line(460, y - 2, 560, y - 2)
                y -= 14

            y = draw_signatures(y)

        p.showPage()
        p.save()
        buffer.seek(0)

        filename = (
            f"Paw #{first_paw} - Formato entrega inventario.pdf"
            if count == 1
            else f"Paw # MULTI ({count}) - Formato entrega inventario.pdf"
        )

        resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
