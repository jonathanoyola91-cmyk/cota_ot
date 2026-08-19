from decimal import Decimal
from html import escape
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db.models import Q

from compras_oil.models import PurchaseRequest
from inventario.models import WorkshopDelivery
from paw_app.models import Paw
from taller.models import EnsambleTaller
from workorders.models import WorkOrder


class Command(BaseCommand):
    help = "Envía alertas de pendientes de Taller al grupo ALERTAS_TALLER."

    def handle(self, *args, **options):
        base_url = getattr(
            settings,
            "IMPETUS_CONTROL_URL",
            "https://www.impetuscontrol.com",
        ).rstrip("/") + "/"

        User = get_user_model()

        destinatarios = list(
            User.objects.filter(
                is_active=True,
                groups__name="ALERTAS_TALLER",
            )
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )

        if not destinatarios:
            self.stdout.write(
                self.style.WARNING(
                    "No hay usuarios activos del grupo ALERTAS_TALLER con correo."
                )
            )
            return

        estados_paw_fuera_operacion = [
            "EN_FACTURACION",
            "FACTURADO",
            "RADICADO",
        ]

        ots = (
            WorkOrder.objects
            .select_related("paw")
            .filter(
                Q(paw__isnull=True)
                | Q(paw__requiere_taller=True)
                | Q(
                    paw__requiere_taller__isnull=True,
                    paw__tipo_operacion="ENSAMBLE",
                )
            )
            .exclude(
                Q(paw__estado_operativo__in=estados_paw_fuera_operacion)
                | Q(
                    estado__in=[
                        WorkOrder.Status.TERMINADA,
                        WorkOrder.Status.CERRADA,
                    ]
                )
            )
            .order_by("-numero")
        )

        pendientes_bom = []
        bom_pendiente_compras = []
        pendientes_horas = []
        pendientes_ensamble = []

        for ot in ots:
            paw = getattr(ot, "paw", None)

            try:
                bom = ot.bom
            except Exception:
                bom = None

            # 1. Falta crear BOM
            if not bom:
                pendientes_bom.append({
                    "ot": ot.numero,
                    "paw": getattr(paw, "numero_paw", "-") if paw else "-",
                    "nombre": getattr(paw, "nombre_paw", "") if paw else "",
                    "url": self._taller_url(base_url),
                })
                continue

            # 2. BOM creado pero aún no hay solicitud de compra
            compra = PurchaseRequest.objects.filter(bom=bom).first()

            estado_bom = str(getattr(bom, "estado", "") or "").upper()

            if estado_bom == "BORRADOR" or not compra:
                bom_pendiente_compras.append({
                    "ot": ot.numero,
                    "paw": getattr(paw, "numero_paw", "-") if paw else "-",
                    "nombre": getattr(paw, "nombre_paw", "") if paw else "",
                    "estado_bom": estado_bom or "SIN SOLICITUD",
                    "url": self._taller_url(base_url),
                })

            # 3. Pendientes de horas
            if paw:
                try:
                    control = paw.ensamble_horas_taller
                except Exception:
                    control = None

                if not control:
                    pendientes_horas.append({
                        "paw": paw.numero_paw,
                        "nombre": paw.nombre_paw or "",
                        "motivo": "Falta iniciar control de horas",
                        "url": self._horas_url(base_url),
                    })
                else:
                    jornadas = control.jornadas.count()

                    if jornadas == 0:
                        pendientes_horas.append({
                            "paw": paw.numero_paw,
                            "nombre": paw.nombre_paw or "",
                            "motivo": "Control iniciado, pero no hay jornadas registradas",
                            "url": urljoin(
                                base_url,
                                f"taller/horas/{control.id}/",
                            ),
                        })
                    elif control.estado != EnsambleTaller.Estado.FINALIZADO:
                        pendientes_horas.append({
                            "paw": paw.numero_paw,
                            "nombre": paw.nombre_paw or "",
                            "motivo": "Hay horas registradas, pero el control sigue EN CURSO",
                            "url": urljoin(
                                base_url,
                                f"taller/horas/{control.id}/",
                            ),
                        })

            # 4. Material 100% entregado a Taller, pero falta ensamblar
            if compra:
                entrega = (
                    WorkshopDelivery.objects
                    .filter(
                        purchase_request=compra,
                        destino="TALLER",
                    )
                    .prefetch_related("lineas")
                    .first()
                )

                if entrega:
                    total_req = Decimal("0")
                    total_ent = Decimal("0")

                    for linea in entrega.lineas.all():
                        requerida = Decimal(linea.cantidad_requerida or 0)
                        entregada = Decimal(linea.cantidad_entregada or 0)

                        if requerida <= 0:
                            continue

                        total_req += requerida
                        total_ent += min(entregada, requerida)

                    material_completo = (
                        total_req > 0
                        and total_ent >= total_req
                    )

                    if material_completo and not getattr(ot, "ensamble_ok", False):
                        pendientes_ensamble.append({
                            "ot": ot.numero,
                            "paw": getattr(paw, "numero_paw", "-") if paw else "-",
                            "nombre": getattr(paw, "nombre_paw", "") if paw else "",
                            "url": self._taller_url(base_url),
                        })

        total = (
            len(pendientes_bom)
            + len(bom_pendiente_compras)
            + len(pendientes_horas)
            + len(pendientes_ensamble)
        )

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "No hay pendientes de Taller que requieran notificación."
                )
            )
            return

        taller_url = self._taller_url(base_url)
        horas_url = self._horas_url(base_url)

        asunto = (
            f"IMPETUS CONTROL · Taller · {total} pendiente"
            f"{'' if total == 1 else 's'}"
        )

        texto = self._crear_texto(
            pendientes_bom,
            bom_pendiente_compras,
            pendientes_horas,
            pendientes_ensamble,
            taller_url,
            horas_url,
        )

        html = self._crear_html(
            pendientes_bom,
            bom_pendiente_compras,
            pendientes_horas,
            pendientes_ensamble,
            taller_url,
            horas_url,
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
                f"Alertas de Taller enviadas a {enviados} usuario(s). "
                f"Sin BOM: {len(pendientes_bom)} | "
                f"BOM/Compras: {len(bom_pendiente_compras)} | "
                f"Horas: {len(pendientes_horas)} | "
                f"Ensamble: {len(pendientes_ensamble)}"
            )
        )

        for error in fallidos:
            self.stdout.write(self.style.WARNING(error))

    def _crear_texto(
        self,
        pendientes_bom,
        bom_pendiente_compras,
        pendientes_horas,
        pendientes_ensamble,
        taller_url,
        horas_url,
    ):
        partes = [
            "IMPETUS CONTROL",
            "",
            "Pendientes de Taller",
            "",
        ]

        if pendientes_bom:
            partes.append("FALTA CREAR BOM")
            for x in pendientes_bom:
                partes.append(
                    f"- OT {x['ot']} | PAW #{x['paw']} | {x['nombre']}"
                )
            partes.append("")

        if bom_pendiente_compras:
            partes.append("BOM PENDIENTE DE PASAR A COMPRAS")
            for x in bom_pendiente_compras:
                partes.append(
                    f"- OT {x['ot']} | PAW #{x['paw']} | "
                    f"{x['nombre']} | Estado BOM: {x['estado_bom']}"
                )
            partes.append("")

        if pendientes_horas:
            partes.append("CONTROL DE HORAS")
            for x in pendientes_horas:
                partes.append(
                    f"- PAW #{x['paw']} | {x['nombre']} | {x['motivo']}"
                )
            partes.append("")

        if pendientes_ensamble:
            partes.append("PENDIENTE DE ENSAMBLE")
            for x in pendientes_ensamble:
                partes.append(
                    f"- OT {x['ot']} | PAW #{x['paw']} | {x['nombre']}"
                )
            partes.append("")

        partes.append(f"Revisar Taller: {taller_url}")
        partes.append(f"Revisar Horas Taller: {horas_url}")
        partes.append("")
        partes.append(
            "Este correo es automático. Las acciones deben realizarse dentro de Impetus Control."
        )

        return "\n".join(partes)

    def _crear_html(
        self,
        pendientes_bom,
        bom_pendiente_compras,
        pendientes_horas,
        pendientes_ensamble,
        taller_url,
        horas_url,
    ):
        secciones = []

        if pendientes_bom:
            filas = "".join(
                f"""
                <tr>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['ot']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">PAW #{escape(str(x['paw']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['nombre']))}</td>
                </tr>
                """
                for x in pendientes_bom
            )
            secciones.append(
                self._tabla(
                    "Falta crear BOM",
                    ["OT", "PAW", "Nombre"],
                    filas,
                    "#dc2626",
                )
            )

        if bom_pendiente_compras:
            filas = "".join(
                f"""
                <tr>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['ot']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">PAW #{escape(str(x['paw']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['nombre']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['estado_bom']))}</td>
                </tr>
                """
                for x in bom_pendiente_compras
            )
            secciones.append(
                self._tabla(
                    "BOM pendiente de enviar a Compras",
                    ["OT", "PAW", "Nombre", "Estado"],
                    filas,
                    "#f97316",
                )
            )

        if pendientes_horas:
            filas = "".join(
                f"""
                <tr>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">PAW #{escape(str(x['paw']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['nombre']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['motivo']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
                        <a href="{x['url']}" style="color:#2563eb;font-weight:700;">Abrir</a>
                    </td>
                </tr>
                """
                for x in pendientes_horas
            )
            secciones.append(
                self._tabla(
                    "Pendientes de control de horas",
                    ["PAW", "Nombre", "Pendiente", "Acción"],
                    filas,
                    "#f59e0b",
                )
            )

        if pendientes_ensamble:
            filas = "".join(
                f"""
                <tr>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['ot']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">PAW #{escape(str(x['paw']))}</td>
                    <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{escape(str(x['nombre']))}</td>
                </tr>
                """
                for x in pendientes_ensamble
            )
            secciones.append(
                self._tabla(
                    "Material completo · Pendiente ensamblar",
                    ["OT", "PAW", "Nombre"],
                    filas,
                    "#2563eb",
                )
            )

        return f"""
        <!doctype html>
        <html>
        <body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a;">
            <div style="max-width:900px;margin:auto;padding:24px;">
                <div style="background:#0f172a;color:#fff;padding:22px 24px;border-radius:14px 14px 0 0;">
                    <div style="font-size:12px;color:#cbd5e1;font-weight:700;">IMPETUS CONTROL</div>
                    <div style="font-size:24px;font-weight:800;margin-top:6px;">Pendientes de Taller</div>
                </div>

                <div style="background:#fff;padding:24px;border-radius:0 0 14px 14px;">
                    <p style="color:#475569;">
                        Resumen de acciones que requieren seguimiento del área de Taller.
                    </p>

                    {''.join(secciones)}

                    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:28px;">
                        <a href="{taller_url}"
                           style="background:#2563eb;color:#fff;padding:12px 18px;border-radius:8px;
                                  text-decoration:none;font-weight:800;">
                            Revisar Taller
                        </a>

                        <a href="{horas_url}"
                           style="background:#16a34a;color:#fff;padding:12px 18px;border-radius:8px;
                                  text-decoration:none;font-weight:800;">
                            Revisar Horas Taller
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

    def _tabla(self, titulo, encabezados, filas, color):
        th = "".join(
            f'<th style="text-align:left;padding:8px;background:#f8fafc;">{escape(h)}</th>'
            for h in encabezados
        )

        return f"""
        <div style="margin-top:22px;border-left:4px solid {color};padding-left:12px;">
            <h3 style="margin:0 0 10px;">{escape(titulo)}</h3>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead><tr>{th}</tr></thead>
                    <tbody>{filas}</tbody>
                </table>
            </div>
        </div>
        """

    @staticmethod
    def _taller_url(base_url):
        return urljoin(base_url, "taller/")

    @staticmethod
    def _horas_url(base_url):
        return urljoin(base_url, "taller/horas/")