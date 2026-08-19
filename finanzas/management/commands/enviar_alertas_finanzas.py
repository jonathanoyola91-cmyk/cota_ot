from decimal import Decimal
from html import escape
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils import timezone

from facturacion.models import Factura
from finanzas.models import FinanceApprovalLine


class Command(BaseCommand):
    help = "Envía alertas de Finanzas y Facturación al grupo ALERTAS_FINANZAS."

    def handle(self, *args, **options):
        base_url = getattr(
            settings,
            "IMPETUS_CONTROL_URL",
            "https://www.impetuscontrol.com",
        ).rstrip("/") + "/"

        hoy = timezone.localdate()

        User = get_user_model()
        destinatarios = list(
            User.objects.filter(
                is_active=True,
                groups__name="ALERTAS_FINANZAS",
            )
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )

        if not destinatarios:
            self.stdout.write(
                self.style.WARNING(
                    "No hay usuarios activos del grupo ALERTAS_FINANZAS con correo."
                )
            )
            return

        pagos = []
        lineas = (
            FinanceApprovalLine.objects
            .select_related(
                "approval",
                "approval__purchase_request",
                "purchase_line",
                "purchase_line__proveedor",
            )
            .filter(pagado=False)
            .order_by("scheduled_date", "-actualizado_en")
        )

        for linea in lineas:
            decision = str(linea.decision or "PENDIENTE").upper()

            if decision not in ("APROBADO", "PROGRAMADO"):
                continue

            compra = linea.approval.purchase_request
            pl = linea.purchase_line

            cantidad = Decimal(pl.cantidad_a_comprar or 0)
            precio = Decimal(pl.precio_unitario or 0)
            subtotal = cantidad * precio
            iva = subtotal * Decimal("0.19")

            tipo = str(linea.tipo_operacion or "COMPRA").upper()
            tasas = {
                "SERVICIO": Decimal("0.04"),
                "COMPRA": Decimal("0.025"),
                "CARGA": Decimal("0.01"),
                "PASAJERO": Decimal("0.035"),
                "NA": Decimal("0"),
            }
            retencion = subtotal * tasas.get(tipo, Decimal("0"))

            total_neto = subtotal + iva - retencion
            porcentaje = Decimal(pl.porcentaje_pago or 0)
            if porcentaje <= 0:
                porcentaje = Decimal("100")

            valor = total_neto * (porcentaje / Decimal("100"))

            estado = "Aprobado para pagar"
            if decision == "PROGRAMADO":
                if linea.scheduled_date:
                    if linea.scheduled_date < hoy:
                        dias = (hoy - linea.scheduled_date).days
                        estado = f"Programado vencido hace {dias} día(s)"
                    elif linea.scheduled_date == hoy:
                        estado = "Programado para hoy"
                    else:
                        dias = (linea.scheduled_date - hoy).days
                        estado = f"Programado en {dias} día(s)"
                else:
                    estado = "Programado sin fecha"

            pagos.append({
                "paw": compra.paw_numero or compra.pk,
                "proveedor": getattr(pl.proveedor, "nombre", "") or "-",
                "codigo": pl.codigo or f"Ítem {pl.pk}",
                "valor": valor,
                "estado": estado,
                "url": urljoin(base_url, f"finanzas/{linea.approval_id}/"),
            })

        facturadas = []
        radicadas = []
        vencidas = []

        facturas = (
            Factura.objects
            .select_related("paw")
            .exclude(estado="pagada")
            .order_by("fecha_vencimiento", "-actualizado_en")
        )

        for factura in facturas:
            data = {
                "paw": factura.numero_paw,
                "cliente": factura.cliente or "-",
                "factura": factura.numero_factura or "Sin número",
                "valor": factura.total_con_iva,
                "vencimiento": factura.fecha_vencimiento,
                "dias": factura.dias_para_vencer,
                "url": urljoin(base_url, f"facturacion/{factura.pk}/"),
            }

            estado = str(factura.estado or "").lower()

            if estado == "vencida":
                vencidas.append(data)
            elif estado == "facturado":
                facturadas.append(data)
            elif estado == "radicacion":
                radicadas.append(data)

        total = len(pagos) + len(facturadas) + len(radicadas) + len(vencidas)

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "No hay pendientes de Finanzas o Facturación."
                )
            )
            return

        finanzas_url = urljoin(base_url, "finanzas/")
        facturacion_url = urljoin(base_url, "facturacion/")

        asunto = f"IMPETUS CONTROL · Finanzas y Facturación · {total} pendientes"

        texto = self._texto(
            pagos, facturadas, radicadas, vencidas,
            finanzas_url, facturacion_url
        )

        html = self._html(
            pagos, facturadas, radicadas, vencidas,
            finanzas_url, facturacion_url
        )

        enviados = 0
        fallidos = []

        for correo in destinatarios:
            try:
                msg = EmailMultiAlternatives(
                    subject=asunto,
                    body=texto,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[correo],
                )
                msg.attach_alternative(html, "text/html")
                enviados += msg.send(fail_silently=False)
            except Exception as exc:
                fallidos.append(f"{correo}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Alertas enviadas a {enviados} usuario(s). "
                f"Pagos: {len(pagos)} | "
                f"Facturadas: {len(facturadas)} | "
                f"Radicadas: {len(radicadas)} | "
                f"Vencidas: {len(vencidas)}"
            )
        )

        for error in fallidos:
            self.stdout.write(self.style.WARNING(error))

    def _texto(self, pagos, facturadas, radicadas, vencidas, finanzas_url, facturacion_url):
        partes = ["IMPETUS CONTROL", "", "Pendientes de Finanzas y Facturación", ""]

        if pagos:
            partes.append("PAGOS PENDIENTES")
            for x in pagos:
                partes.append(
                    f"- PAW #{x['paw']} | {x['proveedor']} | "
                    f"{x['codigo']} | $ {x['valor']:,.0f} | {x['estado']}"
                )
            partes.append(f"Revisar Finanzas: {finanzas_url}")
            partes.append("")

        if facturadas:
            partes.append("FACTURAS PENDIENTES DE RADICAR")
            for x in facturadas:
                partes.append(
                    f"- PAW #{x['paw']} | {x['cliente']} | "
                    f"{x['factura']} | $ {x['valor']:,.0f}"
                )
            partes.append("")

        if radicadas:
            partes.append("FACTURAS RADICADAS PENDIENTES DE PAGO")
            for x in radicadas:
                venc = x["vencimiento"].strftime("%d/%m/%Y") if x["vencimiento"] else "-"
                partes.append(
                    f"- PAW #{x['paw']} | {x['factura']} | "
                    f"Vence {venc} | $ {x['valor']:,.0f}"
                )
            partes.append("")

        if vencidas:
            partes.append("FACTURAS VENCIDAS")
            for x in vencidas:
                dias = abs(x["dias"] or 0)
                partes.append(
                    f"- PAW #{x['paw']} | {x['factura']} | "
                    f"Vencida hace {dias} día(s) | $ {x['valor']:,.0f}"
                )
            partes.append("")

        partes.append(f"Revisar Facturación: {facturacion_url}")
        partes.append("")
        partes.append(
            "Este correo es automático. Las acciones deben realizarse en Impetus Control."
        )

        return "\n".join(partes)

    def _html(self, pagos, facturadas, radicadas, vencidas, finanzas_url, facturacion_url):
        secciones = []

        if pagos:
            filas = "".join(
                f"""
                <tr>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">PAW #{escape(str(x['paw']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(x['proveedor'])}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(x['codigo'])}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">$ {x['valor']:,.0f}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(x['estado'])}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
                        <a href="{x['url']}" style="color:#2563eb;font-weight:700;">Abrir</a>
                    </td>
                </tr>
                """
                for x in pagos
            )
            secciones.append(self._tabla(
                "Pagos pendientes",
                ["PAW", "Proveedor", "Ítem", "Valor", "Estado", "Acción"],
                filas,
            ))
            secciones.append(
                f'<p><a href="{finanzas_url}" style="background:#2563eb;color:#fff;'
                'padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700;">'
                'Revisar Finanzas</a></p>'
            )

        if facturadas:
            filas = "".join(
                self._fila_factura(x, "Pendiente de radicar", "#2563eb")
                for x in facturadas
            )
            secciones.append(self._tabla(
                "Facturas pendientes de radicar",
                ["PAW", "Cliente", "Factura", "Total", "Vencimiento", "Estado", "Acción"],
                filas,
            ))

        if radicadas:
            filas = ""
            for x in radicadas:
                dias = x["dias"]
                if dias is None:
                    estado = "Radicada"
                    color = "#334155"
                elif dias < 0:
                    estado = f"Vencida hace {abs(dias)} día(s)"
                    color = "#dc2626"
                elif dias == 0:
                    estado = "Vence hoy"
                    color = "#f97316"
                elif dias <= 5:
                    estado = f"Vence en {dias} día(s)"
                    color = "#f59e0b"
                else:
                    estado = f"Vence en {dias} día(s)"
                    color = "#16a34a"

                filas += self._fila_factura(x, estado, color)

            secciones.append(self._tabla(
                "Facturas radicadas pendientes de pago",
                ["PAW", "Cliente", "Factura", "Total", "Vencimiento", "Estado", "Acción"],
                filas,
            ))

        if vencidas:
            filas = "".join(
                self._fila_factura(
                    x,
                    f"Vencida hace {abs(x['dias'] or 0)} día(s)",
                    "#dc2626",
                )
                for x in vencidas
            )
            secciones.append(self._tabla(
                "Facturas vencidas",
                ["PAW", "Cliente", "Factura", "Total", "Vencimiento", "Estado", "Acción"],
                filas,
            ))

        return f"""
        <!doctype html>
        <html>
        <body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a;">
            <div style="max-width:950px;margin:auto;padding:24px;">
                <div style="background:#0f172a;color:#fff;padding:22px 24px;border-radius:14px 14px 0 0;">
                    <div style="font-size:12px;color:#cbd5e1;font-weight:700;">IMPETUS CONTROL</div>
                    <div style="font-size:24px;font-weight:800;margin-top:6px;">
                        Pendientes de Finanzas y Facturación
                    </div>
                </div>

                <div style="background:#fff;padding:24px;border-radius:0 0 14px 14px;">
                    <p style="color:#475569;">
                        Resumen de acciones que requieren seguimiento del área financiera.
                    </p>

                    {''.join(secciones)}

                    <div style="text-align:center;margin-top:28px;">
                        <a href="{facturacion_url}"
                           style="background:#16a34a;color:#fff;padding:12px 18px;
                                  border-radius:8px;text-decoration:none;font-weight:800;">
                            Revisar Facturación
                        </a>
                    </div>

                    <p style="margin-top:24px;color:#64748b;font-size:12px;">
                        Este correo es automático. Las acciones deben realizarse dentro de Impetus Control.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def _fila_factura(self, x, estado, color):
        venc = x["vencimiento"].strftime("%d/%m/%Y") if x["vencimiento"] else "-"
        return f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">PAW #{escape(str(x['paw']))}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['cliente']))}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['factura']))}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">$ {x['valor']:,.0f}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{venc}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
                <span style="background:{color};color:#fff;padding:5px 8px;border-radius:999px;
                             font-size:11px;font-weight:800;">
                    {escape(estado)}
                </span>
            </td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
                <a href="{x['url']}" style="color:#2563eb;font-weight:700;">Abrir</a>
            </td>
        </tr>
        """

    def _tabla(self, titulo, encabezados, filas):
        th = "".join(
            f'<th style="text-align:left;padding:8px;background:#f8fafc;">{escape(h)}</th>'
            for h in encabezados
        )
        return f"""
        <div style="margin-top:22px;">
            <h3 style="margin:0 0 10px;">{escape(titulo)}</h3>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead><tr>{th}</tr></thead>
                    <tbody>{filas}</tbody>
                </table>
            </div>
        </div>
        """