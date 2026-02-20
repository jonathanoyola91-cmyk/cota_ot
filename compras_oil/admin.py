# compras_oil/admin.py
from io import BytesIO
from decimal import Decimal
import re

from django.contrib import admin, messages
from django.db import models
from django.http import HttpResponse
from django.utils import timezone
from django import forms

import openpyxl
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import Supplier, PurchaseRequest, PurchaseLine
from inventario.models import InventoryReception, InventoryReceptionLine


# =========================
# PROVEEDORES
# =========================

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "nombre", "nit", "banco", "cuenta_bancaria",
        "tipo_cuenta", "contacto", "telefono", "email"
    )
    search_fields = ("nombre", "nit", "banco")


# =========================
# INLINE: LÍNEAS DE COMPRA
# =========================

class PurchaseLineInlineForm(forms.ModelForm):
    precio_unitario = forms.CharField(required=False)

    class Meta:
        model = PurchaseLine
        fields = "__all__"

    def clean_precio_unitario(self):
        v = self.cleaned_data.get("precio_unitario")
        if not v:
            return None

        s = str(v).replace("COP", "").replace("$", "").replace(" ", "")
        s = re.sub(r"[^0-9,.\-]", "", s)

        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        last_sep = max(last_dot, last_comma)

        if last_sep != -1:
            decimals = s[last_sep + 1:]
            if decimals.isdigit() and len(decimals) <= 2:
                s = re.sub(r"[.,]", "", s[:last_sep]) + "." + decimals
            else:
                s = re.sub(r"[.,]", "", s)

        return Decimal(s)


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    form = PurchaseLineInlineForm
    extra = 0
    can_delete = True

    fields = (
        "plano", "codigo", "descripcion", "unidad",
        "cantidad_requerida", "cantidad_disponible",
        "cantidad_a_comprar", "tipo_pago", "proveedor",
        "precio_unitario", "observaciones_bom",
        "observaciones_compras",
    )

    readonly_fields = (
        "plano", "codigo", "descripcion", "unidad",
        "cantidad_requerida", "cantidad_a_comprar",
        "observaciones_bom",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(cantidad_requerida__lte=Decimal("0"))

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields["precio_unitario"] = forms.CharField(required=False)
        return formset

    def has_add_permission(self, request, obj=None):
        return False


# =========================
# SOLICITUD DE COMPRA
# =========================

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):

    list_display = (
        "paw_numero", "paw_nombre", "bom", "estado",
        "tipo_pago", "estado_finanzas",
        "subtotal_requerido", "total_paw",
        "creado_por", "actualizado_en",
    )

    list_filter = ("estado", "tipo_pago", "finance_approval__estado")

    search_fields = (
        "bom__workorder__numero",
        "paw_numero", "paw_nombre",
    )

    inlines = [PurchaseLineInline]

    actions = [
        "marcar_en_revision",
        "cerrar_solicitud",
        "enviar_a_finanzas",
        "enviar_a_aprobacion_compras",
        "enviar_a_inventario",
        "descargar_pdf",
        "descargar_excel",
    ]

    readonly_fields = (
        "creado_por", "creado_en",
        "actualizado_en", "paw_numero", "paw_nombre",
    )

    # ---------- helpers ----------

    def _fmt(self, value: Decimal):
        return f"{int(value):,}".replace(",", ".")

    @admin.display(description="Estado Finanzas")
    def estado_finanzas(self, obj):
        fa = getattr(obj, "finance_approval", None)
        return fa.estado if fa else "—"

    @admin.display(description="Subtotal requerido")
    def subtotal_requerido(self, obj):
        total = Decimal("0")
        for ln in obj.lineas.all():
            total += (ln.cantidad_requerida or 0) * (ln.precio_unitario or 0)
        return self._fmt(total)

    @admin.display(description="Total PAW")
    def total_paw(self, obj):
        total = Decimal("0")
        for ln in obj.lineas.all():
            total += (ln.cantidad_a_comprar or 0) * (ln.precio_unitario or 0)
        return self._fmt(total)

    def save_model(self, request, obj, form, change):
        if not obj.creado_por:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    # =========================
    # ACCIONES
    # =========================

    @admin.action(description="Marcar como EN REVISIÓN")
    def marcar_en_revision(self, request, queryset):
        queryset.update(estado="EN_REVISION")

    @admin.action(description="Cerrar solicitud")
    def cerrar_solicitud(self, request, queryset):
        for pr in queryset:
            pr.estado = "CERRADA"
            pr.save(update_fields=["estado", "actualizado_en"])

    @admin.action(description="Enviar a Finanzas")
    def enviar_a_finanzas(self, request, queryset):
        from finanzas.models import FinanceApproval

        for pr in queryset:
            FinanceApproval.objects.get_or_create(
                purchase_request=pr,
                defaults={
                    "estado": FinanceApproval.Estado.PENDIENTE,
                    "enviado_por": request.user,
                    "enviado_en": timezone.now(),
                },
            )

    @admin.action(description="Enviar a Aprobación de Compras")
    def enviar_a_aprobacion_compras(self, request, queryset):
        from aprobacion.models import PurchaseApproval
        from aprobacion.admin import sync_purchase_approval_lines

        for pr in queryset:
            pa, created = PurchaseApproval.objects.get_or_create(
                purchase_request=pr,
                defaults={
                    "estado": PurchaseApproval.Estado.PENDIENTE,
                    "enviado_por": request.user,
                    "enviado_en": timezone.now(),
                },
            )

            if not created:
                pa.enviado_por = request.user
                pa.enviado_en = timezone.now()
                pa.save(update_fields=["enviado_por", "enviado_en", "actualizado_en"])

            sync_purchase_approval_lines(pa, refresh_pending_only=True)
            pa.recalcular_estado()
            pa.save(update_fields=["estado", "actualizado_en"])

    @admin.action(description="Enviar a Inventario")
    def enviar_a_inventario(self, request, queryset):
        for pr in queryset:
            recepcion, _ = InventoryReception.objects.get_or_create(
                purchase_request=pr,
                defaults={"creado_por": request.user},
            )

            for ln in pr.lineas.all():
                InventoryReceptionLine.objects.get_or_create(
                    recepcion=recepcion,
                    purchase_line=ln,
                    defaults={
                        "cantidad_esperada": ln.cantidad_a_comprar or 0,
                        "cantidad_recibida": 0,
                        "estado": "PENDIENTE",
                    },
                )

    # =========================
    # EXPORT EXCEL
    # =========================

    @admin.action(description="Descargar PAW en Excel")
    def descargar_excel(self, request, queryset):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "PAW"

        headers = [
            "PAW", "Nombre", "OT", "Estado", "Tipo Pago",
            "Código", "Descripción", "Unidad",
            "Req", "Disp", "Comprar",
            "Proveedor", "Precio", "Valor",
        ]
        ws.append(headers)

        for pr in queryset:
            for ln in pr.lineas.all():
                ws.append([
                    pr.paw_numero,
                    pr.paw_nombre,
                    getattr(pr.bom.workorder, "numero", ""),
                    pr.estado,
                    pr.tipo_pago,
                    ln.codigo,
                    ln.descripcion,
                    ln.unidad,
                    float(ln.cantidad_requerida or 0),
                    float(ln.cantidad_disponible or 0),
                    float(ln.cantidad_a_comprar or 0),
                    ln.proveedor.nombre if ln.proveedor else "",
                    float(ln.precio_unitario or 0),
                    float((ln.cantidad_a_comprar or 0) * (ln.precio_unitario or 0)),
                ])

        out = BytesIO()
        wb.save(out)
        out.seek(0)

        return HttpResponse(
            out.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # =========================
    # EXPORT PDF
    # =========================

    @admin.action(description="Descargar PAW en PDF")
    def descargar_pdf(self, request, queryset):
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        y = height - 40
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, "PAW - Solicitud de Compra")
        y -= 25

        qs = queryset.select_related("bom__workorder").prefetch_related("lineas__proveedor")

        for pr in qs:
            if y < 140:
                p.showPage()
                y = height - 40

            # ---------- ENCABEZADO ----------
            ot = getattr(pr.bom.workorder, "numero", "-")
            p.setFont("Helvetica-Bold", 10)
            p.drawString(40, y, f"PAW #{pr.paw_numero} - {pr.paw_nombre}")
            y -= 14
            p.setFont("Helvetica", 9)
            p.drawString(40, y, f"OT: {ot} | Estado: {pr.estado} | Tipo Pago: {pr.tipo_pago or '-'}")
            y -= 18

            # ---------- CABECERA TABLA ----------
            p.setFont("Helvetica-Bold", 8)
            p.drawString(40, y, "CÓDIGO")
            p.drawString(95, y, "DESCRIPCIÓN")
            p.drawRightString(360, y, "REQ")
            p.drawRightString(405, y, "DISP")
            p.drawRightString(450, y, "COMPR")
            p.drawRightString(505, y, "P.UNIT")
            p.drawRightString(560, y, "VALOR")
            y -= 12

            p.setFont("Helvetica", 8)

            # ---------- FILAS ----------
            for ln in pr.lineas.all():
                if y < 90:
                    p.showPage()
                    y = height - 40

                    # repetir cabecera
                    p.setFont("Helvetica-Bold", 8)
                    p.drawString(40, y, "CÓDIGO")
                    p.drawString(95, y, "DESCRIPCIÓN")
                    p.drawRightString(360, y, "REQ")
                    p.drawRightString(405, y, "DISP")
                    p.drawRightString(450, y, "COMPR")
                    p.drawRightString(505, y, "P.UNIT")
                    p.drawRightString(560, y, "VALOR")
                    y -= 12
                    p.setFont("Helvetica", 8)

                req = ln.cantidad_requerida or 0
                disp = ln.cantidad_disponible or 0
                compr = ln.cantidad_a_comprar or 0
                price = ln.precio_unitario or 0
                value = compr * price

                p.drawString(40, y, (ln.codigo or "")[:12])
                p.drawString(95, y, (ln.descripcion or "")[:35])
                p.drawRightString(360, y, f"{req}")
                p.drawRightString(405, y, f"{disp}")
                p.drawRightString(450, y, f"{compr}")
                p.drawRightString(505, y, f"{price}")
                p.drawRightString(560, y, f"{value}")
                y -= 12

            y -= 10

        p.showPage()
        p.save()
        buffer.seek(0)

        return HttpResponse(buffer.getvalue(), content_type="application/pdf")
