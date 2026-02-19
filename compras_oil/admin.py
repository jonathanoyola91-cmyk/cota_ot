# Compras_oil/admin.py
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


# ---------------- PROVEEDORES ----------------

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "nit",
        "banco",
        "cuenta_bancaria",
        "tipo_cuenta",
        "contacto",
        "telefono",
        "email",
    )
    search_fields = ("nombre", "nit", "banco")


# ---------------- LINEAS DE COMPRA (INLINE) ----------------

class PurchaseLineInlineForm(forms.ModelForm):
    """
    precio_unitario se captura como texto para permitir:
    "$ 250.000" / "250.000,50" / "250000"
    y luego se convierte a Decimal en clean_precio_unitario().
    """
    precio_unitario = forms.CharField(required=False)

    class Meta:
        model = PurchaseLine
        fields = "__all__"

    def clean_precio_unitario(self):
        v = self.cleaned_data.get("precio_unitario")
        if v in (None, ""):
            return None

        s = str(v)

        # quitar símbolos y espacios (incluye NBSP)
        s = s.replace("COP", "").replace("$", "")
        s = s.replace("\u00A0", " ").strip()
        s = s.replace(" ", "")

        # dejar solo dígitos, separadores y signo
        s = re.sub(r"[^0-9,.\-]", "", s)

        if s in ("", "-", ",", "."):
            return None

        # Regla robusta:
        # el separador decimal es el ÚLTIMO (.,) SOLO si tiene 1 o 2 dígitos después
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        last_sep = max(last_dot, last_comma)

        if last_sep != -1:
            decimals = s[last_sep + 1:]
            if decimals.isdigit() and 1 <= len(decimals) <= 2:
                int_part = re.sub(r"[.,]", "", s[:last_sep])  # quita miles
                s = f"{int_part}.{decimals}"
            else:
                # no parece decimal => todo separador es miles
                s = re.sub(r"[.,]", "", s)
        else:
            # sin separadores
            pass

        try:
            return Decimal(s)
        except Exception:
            raise forms.ValidationError("Precio unitario inválido. Ej: 250000 o 250000,50")


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    form = PurchaseLineInlineForm
    extra = 0
    can_delete = True

    fields = (
        "plano",
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_disponible",
        "cantidad_a_comprar",
        "tipo_pago",
        "proveedor",
        "precio_unitario",
        "observaciones_bom",
        "observaciones_compras",
    )

    readonly_fields = (
        "plano",
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_a_comprar",
        "observaciones_bom",
    )

    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(
                attrs={"rows": 1, "style": "width:220px; resize:horizontal;"}
            )
        }
    }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # ✅ Ocultar items con cantidad requerida en 0 (o menor)
        return qs.exclude(cantidad_requerida__lte=Decimal("0"))

    def get_formset(self, request, obj=None, **kwargs):
        """
        ✅ Blindaje extra: fuerza el campo a CharField dentro del formset.
        Esto evita que Django lo trate como DecimalField y dispare:
        "el valor debe ser un número decimal"
        """
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields["precio_unitario"] = forms.CharField(required=False)
        return formset

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "plano":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:90px;"})

        elif db_field.name == "codigo":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:90px;"})

        elif db_field.name == "unidad":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:60px; text-align:center;"}
            )

        elif db_field.name in ("cantidad_requerida", "cantidad_disponible", "cantidad_a_comprar"):
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:70px; text-align:right;"}
            )

        elif db_field.name == "precio_unitario":
            # ✅ Forzar CharField (si no, Django valida como Decimal antes del clean)
            kwargs["form_class"] = forms.CharField
            kwargs["required"] = False
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:130px; text-align:right;", "inputmode": "numeric"}
            )

        return super().formfield_for_dbfield(db_field, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields
        if request.user.groups.filter(name="COMPRAS_OIL").exists():
            return self.readonly_fields
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name="COMPRAS_OIL").exists():
            if obj is None:
                return True
            return obj.estado != "CERRADA"
        return False


# ---------------- SOLICITUD DE COMPRA ----------------

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "paw_numero",
        "paw_nombre",
        "bom",
        "estado",
        "tipo_pago",
        "estado_finanzas",
        "subtotal_requerido",
        "total_paw",
        "creado_por",
        "actualizado_en",
    )

    list_filter = ("estado", "tipo_pago", "finance_approval__estado")

    search_fields = (
        "bom__workorder__numero",
        "bom__template__nombre",
        "paw_numero",
        "paw_nombre",
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
        "creado_por",
        "creado_en",
        "actualizado_en",
        "paw_numero",
        "paw_nombre",
    )

    class Media:
        js = ("Compras_oil/js/precio_unitario_format.js",)

    @admin.display(description="PAW Número")
    def paw_numero(self, obj):
        return obj.paw_numero or "-"

    @admin.display(description="PAW Nombre")
    def paw_nombre(self, obj):
        return obj.paw_nombre or "-"

    @admin.display(description="Estado Finanzas")
    def estado_finanzas(self, obj):
        fa = getattr(obj, "finance_approval", None)
        return fa.estado if fa else "—"

    @admin.display(description="Subtotal requerido")
    def subtotal_requerido(self, obj):
        total = 0
        for ln in obj.lineas.all():
            qty = ln.cantidad_requerida or 0
            price = ln.precio_unitario or 0
            total += qty * price
        return total

    @admin.display(description="Total PAW")
    def total_paw(self, obj):
        total = 0
        for ln in obj.lineas.all():
            qty = ln.cantidad_a_comprar or 0
            price = ln.precio_unitario or 0
            total += qty * price
        return total

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return list(self.readonly_fields)
        if request.user.groups.filter(name="COMPRAS_OIL").exists():
            return list(self.readonly_fields)
        return [f.name for f in self.model._meta.fields]

    def save_model(self, request, obj, form, change):
        if not obj.creado_por:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    # ---------------- ACCIONES ----------------

    @admin.action(description="Marcar como EN REVISIÓN")
    def marcar_en_revision(self, request, queryset):
        updated = queryset.update(estado="EN_REVISION")
        messages.success(request, f"{updated} solicitud(es) en revisión.")

    @admin.action(description="Cerrar solicitud de compra")
    def cerrar_solicitud(self, request, queryset):
        cerradas = 0
        for req in queryset:
            if req.estado != "CERRADA":
                req.estado = "CERRADA"
                req.save(update_fields=["estado", "actualizado_en"])
                cerradas += 1
        messages.success(request, f"{cerradas} solicitud(es) cerradas.")

    @admin.action(description="Enviar a Finanzas")
    def enviar_a_finanzas(self, request, queryset):
        if not (
            request.user.is_superuser
            or request.user.groups.filter(name="COMPRAS_OIL").exists()
        ):
            messages.error(request, "No tienes permisos para enviar solicitudes a Finanzas.")
            return

        try:
            from finanzas.models import FinanceApproval
        except Exception as e:
            messages.error(request, f"No se pudo importar finanzas.FinanceApproval. Error: {e}")
            return

        enviados = 0
        for pr in queryset:
            fa, created = FinanceApproval.objects.get_or_create(
                purchase_request=pr,
                defaults={
                    "estado": FinanceApproval.Estado.PENDIENTE,
                    "enviado_por": request.user,
                    "enviado_en": timezone.now(),
                },
            )

            if not created:
                fa.estado = FinanceApproval.Estado.PENDIENTE
                fa.enviado_por = request.user
                fa.enviado_en = timezone.now()
                fa.save(update_fields=["estado", "enviado_por", "enviado_en", "actualizado_en"])

            enviados += 1

        messages.success(request, f"{enviados} solicitud(es) enviadas a Finanzas.")

    @admin.action(description="Enviar a Aprobación de Compras (Finanzas)")
    def enviar_a_aprobacion_compras(self, request, queryset):
        if not (
            request.user.is_superuser
            or request.user.groups.filter(name="COMPRAS_OIL").exists()
        ):
            messages.error(request, "No tienes permisos para enviar solicitudes a Aprobación de Compras.")
            return

        try:
            from aprobacion.models import PurchaseApproval
        except Exception as e:
            messages.error(request, f"No se pudo importar aprobacion.PurchaseApproval. Error: {e}")
            return

        enviados = 0
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
                pa.estado = PurchaseApproval.Estado.PENDIENTE
                pa.enviado_por = request.user
                pa.enviado_en = timezone.now()
                pa.save(update_fields=["estado", "enviado_por", "enviado_en", "actualizado_en"])

            enviados += 1

        messages.success(request, f"{enviados} solicitud(es) enviadas a Aprobación de Compras.")

    @admin.action(description="Enviar a Inventario (crear recepción por línea)")
    def enviar_a_inventario(self, request, queryset):
        if not (
            request.user.is_superuser
            or request.user.groups.filter(name="COMPRAS_OIL").exists()
        ):
            messages.error(request, "No tienes permisos para enviar solicitudes a Inventario.")
            return

        enviados = 0
        for pr in queryset:
            recepcion, _ = InventoryReception.objects.get_or_create(
                purchase_request=pr,
                defaults={"creado_por": request.user},
            )

            for line in pr.lineas.all():
                InventoryReceptionLine.objects.get_or_create(
                    recepcion=recepcion,
                    purchase_line=line,
                    defaults={
                        "cantidad_esperada": line.cantidad_a_comprar or 0,
                        "cantidad_recibida": 0,
                        "estado": "PENDIENTE",
                    },
                )

            enviados += 1

        messages.success(request, f"Enviadas {enviados} solicitud(es) a Inventario.")

    # ---------------- EXPORTS (PDF / EXCEL) ----------------

    @admin.action(description="Descargar PAW en Excel")
    def descargar_excel(self, request, queryset):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "PAW"

        headers = [
            "Paw #", "PAW Nombre", "OT", "Estado Compra", "Tipo Pago Encabezado",
            "Plano", "Código", "Descripción", "Unidad",
            "Cant. requerida", "Cant. disponible", "Cant. a comprar",
            "Tipo pago ítem", "Proveedor",
            "Precio unitario", "Valor ítem",
            "Obs BOM", "Obs Compras",
        ]
        ws.append(headers)

        qs = queryset.select_related("bom__workorder").prefetch_related("lineas__proveedor")

        grand_total = 0
        paw_nums = []

        for pr in qs:
            paw_nums.append(pr.paw_numero or str(pr.id))

            try:
                ot_num = pr.bom.workorder.numero
            except Exception:
                ot_num = "-"

            total_pr = 0

            for ln in pr.lineas.all():
                qty = ln.cantidad_a_comprar or 0
                price = ln.precio_unitario or 0
                item_value = qty * price
                total_pr += item_value

                ws.append([
                    pr.paw_numero or "",
                    pr.paw_nombre or "",
                    ot_num,
                    pr.estado,
                    pr.tipo_pago or "",
                    ln.plano or "",
                    ln.codigo or "",
                    ln.descripcion or "",
                    ln.unidad or "",
                    float(ln.cantidad_requerida or 0),
                    float(ln.cantidad_disponible or 0),
                    float(qty),
                    ln.tipo_pago or "",
                    (ln.proveedor.nombre if ln.proveedor else ""),
                    float(price or 0),
                    float(item_value or 0),
                    (ln.observaciones_bom or ""),
                    (ln.observaciones_compras or ""),
                ])

            ws.append([""] * len(headers))
            ws.append([""] * 14 + ["TOTAL PAW:", float(total_pr)] + ["", ""])
            ws.append([""] * len(headers))

            grand_total += total_pr

        ws.append([""] * 14 + ["TOTAL GENERAL:", float(grand_total)] + ["", ""])

        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 18

        out = BytesIO()
        wb.save(out)
        out.seek(0)

        filename = f'Paw # MULTI ({len(paw_nums)}) - export.xlsx' if len(paw_nums) > 1 else f'Paw #{paw_nums[0]} - export.xlsx'
        resp = HttpResponse(
            out.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @admin.action(description="Descargar PAW en PDF")
    def descargar_pdf(self, request, queryset):
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        y = height - 40
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, "Export PAW - Purchase Requests")
        y -= 25

        qs = queryset.select_related("bom__workorder").prefetch_related("lineas__proveedor")

        paw_nums = []
        grand_total = 0

        for pr in qs:
            paw_nums.append(pr.paw_numero or str(pr.id))

            if y < 160:
                p.showPage()
                y = height - 40

            try:
                ot_num = pr.bom.workorder.numero
            except Exception:
                ot_num = "-"

            p.setFont("Helvetica-Bold", 10)
            p.drawString(40, y, f"Paw #: {pr.paw_numero or '-'} | {pr.paw_nombre or ''} | OT: {ot_num}")
            y -= 14
            p.setFont("Helvetica", 9)
            p.drawString(40, y, f"Estado Compra: {pr.estado} | Tipo Pago Encabezado: {pr.tipo_pago or '-'}")
            y -= 16

            # Encabezados con cantidades requerida/disponible/a comprar y precio unitario
            p.setFont("Helvetica-Bold", 8)
            p.drawString(40, y, "PLANO")
            p.drawString(90, y, "COD")
            p.drawString(135, y, "DESCRIPCIÓN")

            p.drawRightString(395, y, "REQ")
            p.drawRightString(435, y, "DISP")
            p.drawRightString(480, y, "COMPR")

            p.drawRightString(525, y, "P.UNIT")
            p.drawRightString(560, y, "VALOR")
            y -= 12

            p.setFont("Helvetica", 8)

            total_pr = 0

            for ln in pr.lineas.all():
                if y < 90:
                    p.showPage()
                    y = height - 40
                    p.setFont("Helvetica", 8)

                    # Repetir encabezado
                    p.setFont("Helvetica-Bold", 8)
                    p.drawString(40, y, "PLANO")
                    p.drawString(90, y, "COD")
                    p.drawString(135, y, "DESCRIPCIÓN")
                    p.drawRightString(395, y, "REQ")
                    p.drawRightString(435, y, "DISP")
                    p.drawRightString(480, y, "COMPR")
                    p.drawRightString(525, y, "P.UNIT")
                    p.drawRightString(560, y, "VALOR")
                    y -= 12
                    p.setFont("Helvetica", 8)

                req = ln.cantidad_requerida or 0
                disp = ln.cantidad_disponible or 0
                compr = ln.cantidad_a_comprar or 0
                price = ln.precio_unitario or 0
                item_value = compr * price
                total_pr += item_value

                plano = (ln.plano or "")[:8]
                cod = (ln.codigo or "")[:10]
                desc = (ln.descripcion or "")[:30]

                p.drawString(40, y, plano)
                p.drawString(90, y, cod)
                p.drawString(135, y, desc)

                p.drawRightString(395, y, f"{req}")
                p.drawRightString(435, y, f"{disp}")
                p.drawRightString(480, y, f"{compr}")
                p.drawRightString(525, y, f"{price}")
                p.drawRightString(560, y, f"{item_value}")
                y -= 12

            y -= 6
            p.setFont("Helvetica-Bold", 10)
            p.drawRightString(560, y, f"TOTAL PAW: {total_pr}")
            p.setFont("Helvetica", 9)
            y -= 18

            grand_total += total_pr

        if len(paw_nums) > 1:
            if y < 90:
                p.showPage()
                y = height - 40
            p.setFont("Helvetica-Bold", 11)
            p.drawRightString(560, y, f"TOTAL GENERAL: {grand_total}")
            y -= 20

        p.showPage()
        p.save()
        buffer.seek(0)

        filename = f'Paw # MULTI ({len(paw_nums)}) - export.pdf' if len(paw_nums) > 1 else f'Paw #{paw_nums[0]} - export.pdf'
        resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
