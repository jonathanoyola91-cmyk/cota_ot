from django.contrib import admin, messages
from django.db import models
from django.utils import timezone
from django.http import HttpResponse

from .models import Supplier, PurchaseRequest, PurchaseLine
from inventario.models import InventoryReception, InventoryReceptionLine

# Excel
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

# PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


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


# ---------------- LINEAS DE COMPRA ----------------

class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 0

    fields = (
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_disponible",
        "cantidad_a_comprar",
        "tipo_pago",            # ✅ NUEVO: Crédito/Contado por ítem
        "proveedor",
        "precio_unitario",
        "observaciones_bom",
        "observaciones_compras",
    )

    readonly_fields = (
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_a_comprar",
        "observaciones_bom",
        # ✅ NO pongas tipo_pago aquí
    )

    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(
                attrs={"rows": 1, "style": "width:220px; resize:horizontal;"}
            )
        }
    }

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "codigo":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:90px;"}
            )
        elif db_field.name == "unidad":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:60px; text-align:center;"}
            )
        elif db_field.name in (
            "cantidad_disponible",
            "cantidad_requerida",
            "cantidad_a_comprar",
        ):
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:70px; text-align:right;"}
            )
        elif db_field.name == "precio_unitario":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:90px; text-align:right;"}
            )
        # ✅ No se necesita widget para tipo_pago: Django lo renderiza como <select> automáticamente

        return super().formfield_for_dbfield(db_field, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields

        if request.user.groups.filter(name="COMPRAS_OIL").exists():
            return self.readonly_fields

        return [f.name for f in self.model._meta.fields]


# ---------------- SOLICITUD DE COMPRA ----------------

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "paw_numero",
        "paw_nombre",
        "bom",
        "estado",
        "tipo_pago",
        "creado_por",
        "actualizado_en",
    )
    list_filter = ("estado", "tipo_pago")
    search_fields = (
        "bom__workorder__numero",
        "bom__template__nombre",
        "bom__workorder__paw__numero_paw",
        "bom__workorder__paw__nombre_paw",
        "paw_numero",
        "paw_nombre",
    )

    inlines = [PurchaseLineInline]

    actions = [
        "marcar_en_revision",
        "cerrar_solicitud",
        "enviar_a_finanzas",
        "enviar_a_inventario",
        "descargar_paw_pdf",
        "descargar_paw_excel",
    ]

    readonly_fields = (
        "creado_por",
        "creado_en",
        "actualizado_en",
        "paw_numero",
        "paw_nombre",
    )

    @admin.display(description="PAW Número")
    def paw_numero(self, obj):
        return obj.paw_numero or "-"

    @admin.display(description="PAW Nombre")
    def paw_nombre(self, obj):
        return obj.paw_nombre or "-"

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return list(self.readonly_fields)

        if request.user.groups.filter(name="COMPRAS_OIL").exists():
            if obj and obj.estado == "CERRADA":
                return [f.name for f in self.model._meta.fields]
            return list(self.readonly_fields)

        return [f.name for f in self.model._meta.fields]

    # ---------------- EXPORTS (PDF / EXCEL) ----------------

    @admin.action(description="Descargar PAW (PDF) - Seleccionar 1")
    def descargar_paw_pdf(self, request, queryset):
        if queryset.count() != 1:
            messages.warning(request, "Selecciona SOLO 1 Purchase Request para descargar en PDF.")
            return

        pr = queryset.first()
        bom = pr.bom
        wo = getattr(bom, "workorder", None)
        template = getattr(bom, "template", None)

        filename = f"PAW_{pr.paw_numero or 'SIN_NUM'}_PR_{pr.pk}.pdf"

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        doc = SimpleDocTemplate(response, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("IMPETUS CONTROL - Solicitud de Compra", styles["Title"]))
        story.append(Spacer(1, 10))

        header_data = [
            ["PAW #", pr.paw_numero or "-", "Nombre", pr.paw_nombre or "-"],
            ["OT #", getattr(wo, "numero", "-") if wo else "-", "OT", getattr(wo, "titulo", "-") if wo else "-"],
            ["BOM", str(bom) if bom else "-", "Plantilla", getattr(template, "nombre", "-") if template else "-"],
            ["Estado PR", pr.estado, "Tipo Pago (Encabezado)", pr.tipo_pago or "-"],
        ]

        header_table = Table(header_data, colWidths=[90, 160, 140, 160])
        header_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 12))

        data = [[
            "Código", "Descripción", "Und",
            "Req", "Disp", "Comprar",
            "Tipo Pago",
            "Proveedor", "Precio",
            "Obs BOM", "Obs Compras"
        ]]

        for line in pr.lineas.all().order_by("id"):
            data.append([
                line.codigo or "",
                line.descripcion or "",
                line.unidad or "",
                str(line.cantidad_requerida or 0),
                str(line.cantidad_disponible or 0),
                str(line.cantidad_a_comprar or 0),
                line.get_tipo_pago_display() if getattr(line, "tipo_pago", None) else "",
                line.proveedor.nombre if line.proveedor else "",
                str(line.precio_unitario) if line.precio_unitario is not None else "",
                (line.observaciones_bom or "")[:60],
                (line.observaciones_compras or "")[:60],
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)

        doc.build(story)
        return response

    @admin.action(description="Descargar PAW (Excel) - Seleccionar 1")
    def descargar_paw_excel(self, request, queryset):
        if queryset.count() != 1:
            messages.warning(request, "Selecciona SOLO 1 Purchase Request para descargar en Excel.")
            return

        pr = queryset.first()
        bom = pr.bom
        wo = getattr(bom, "workorder", None)
        template = getattr(bom, "template", None)

        wb = Workbook()
        ws = wb.active
        ws.title = "Solicitud Compra"

        # Encabezado
        ws.append(["PAW #", pr.paw_numero or ""])
        ws.append(["Nombre PAW", pr.paw_nombre or ""])
        ws.append(["OT #", getattr(wo, "numero", "") if wo else ""])
        ws.append(["OT Título", getattr(wo, "titulo", "") if wo else ""])
        ws.append(["BOM", str(bom) if bom else ""])
        ws.append(["Plantilla", getattr(template, "nombre", "") if template else ""])
        ws.append(["Estado PR", pr.estado])
        ws.append(["Tipo Pago (Encabezado)", pr.tipo_pago or ""])
        ws.append(["Actualizado", timezone.localtime(pr.actualizado_en).strftime("%Y-%m-%d %H:%M")])
        ws.append([])

        headers = [
            "Código", "Descripción", "Unidad",
            "Cantidad Requerida", "Disponible", "A Comprar",
            "Tipo Pago",
            "Proveedor", "Precio Unitario",
            "Obs BOM", "Obs Compras"
        ]
        ws.append(headers)

        for line in pr.lineas.all().order_by("id"):
            ws.append([
                line.codigo or "",
                line.descripcion or "",
                line.unidad or "",
                float(line.cantidad_requerida or 0),
                float(line.cantidad_disponible or 0),
                float(line.cantidad_a_comprar or 0),
                line.get_tipo_pago_display() if getattr(line, "tipo_pago", None) else "",
                line.proveedor.nombre if line.proveedor else "",
                float(line.precio_unitario) if line.precio_unitario is not None else "",
                line.observaciones_bom or "",
                line.observaciones_compras or "",
            ])

        widths = [14, 45, 10, 18, 12, 12, 12, 22, 14, 25, 25]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

        filename = f"PAW_{pr.paw_numero or 'SIN_NUM'}_PR_{pr.pk}.xlsx"
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

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

    @admin.action(description="Enviar a Inventario (crear recepción por línea)")
    def enviar_a_inventario(self, request, queryset):
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
