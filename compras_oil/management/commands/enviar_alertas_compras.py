from decimal import Decimal
from html import escape
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from compras_oil.models import PurchaseRequest
from inventario.models import InventoryReceptionLine


class Command(BaseCommand):
    help = "Envía alertas por correo de pendientes que requieren acción de Compras."

    def handle(self, *args, **options):

        base_url = getattr(
            settings,
            "IMPETUS_CONTROL_URL",
            "https://www.impetuscontrol.com",
        ).rstrip("/") + "/"

        # =====================================================
        # COMPRAS ACTIVAS
        # =====================================================
        compras = (
            PurchaseRequest.objects
            .exclude(estado="CERRADA")
            .select_related(
                "bom",
                "bom__workorder",
            )
            .prefetch_related(
                "lineas__proveedor",
                "lineas__finance_line",
                "lineas__purchase_approval_line",
            )
            .order_by("-actualizado_en")
        )

        # =====================================================
        # LÍNEAS YA ENVIADAS A INVENTARIO
        # =====================================================
        lineas_en_inventario = set(
            InventoryReceptionLine.objects.values_list(
                "purchase_line_id",
                flat=True,
            )
        )

        pendientes_por_paw = []
        total_pendientes = 0

        # =====================================================
        # ANALIZAR CADA PAW
        # =====================================================
        for compra in compras:

            pendientes = []

            for linea in compra.lineas.all():

                cantidad = Decimal(
                    linea.cantidad_a_comprar or 0
                )

                # No requiere compra
                if cantidad <= 0:
                    continue

                motivo = self._obtener_motivo(
                    linea,
                    lineas_en_inventario,
                )

                if motivo:

                    pendientes.append({
                        "codigo": (
                            linea.codigo
                            or f"Ítem {linea.id}"
                        ),
                        "descripcion": (
                            linea.descripcion
                            or ""
                        ),
                        "motivo": motivo,
                    })

            # Si el PAW tiene algo que Compras debe atender
            if pendientes:

                total_pendientes += len(pendientes)

                paw_url = urljoin(
                    base_url,
                    f"compras/paw/{compra.pk}/",
                )

                pendientes_por_paw.append({
                    "paw_numero": (
                        compra.paw_numero
                        or compra.pk
                    ),
                    "paw_nombre": (
                        compra.paw_nombre
                        or ""
                    ),
                    "url": paw_url,
                    "pendientes": pendientes,
                })

        # =====================================================
        # NO HAY PENDIENTES
        # =====================================================
        if not pendientes_por_paw:

            self.stdout.write(
                self.style.SUCCESS(
                    "No hay pendientes de Compras "
                    "que requieran notificación."
                )
            )

            return

        # =====================================================
        # USUARIOS DEL GRUPO COMPRAS
        # =====================================================
        User = get_user_model()

        destinatarios = list(
            User.objects.filter(
                is_active=True,
                groups__name="COMPRAS",
            )
            .exclude(email="")
            .values_list(
                "email",
                flat=True,
            )
            .distinct()
        )

        if not destinatarios:

            self.stdout.write(
                self.style.WARNING(
                    "Hay pendientes, pero no hay "
                    "usuarios activos del grupo COMPRAS "
                    "con correo registrado."
                )
            )

            return

        dashboard_url = urljoin(
            base_url,
            "compras/",
        )

        # =====================================================
        # ASUNTO
        # =====================================================
        asunto = (
            f"IMPETUS CONTROL · "
            f"{total_pendientes} pendiente"
            f"{'' if total_pendientes == 1 else 's'} "
            f"de Compras"
        )

        # =====================================================
        # TEXTO PLANO
        # =====================================================
        texto = self._crear_texto(
            pendientes_por_paw,
            total_pendientes,
            dashboard_url,
        )

        # =====================================================
        # HTML
        # =====================================================
        html = self._crear_html(
            pendientes_por_paw,
            total_pendientes,
            dashboard_url,
        )

        # =====================================================
        # ENVIAR CORREOS
        # =====================================================
        enviados = 0

        for correo in destinatarios:

            mensaje = EmailMultiAlternatives(
                subject=asunto,
                body=texto,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[correo],
            )

            mensaje.attach_alternative(
                html,
                "text/html",
            )

            enviados += mensaje.send(
                fail_silently=False
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Alertas enviadas correctamente "
                f"a {enviados} usuario(s). "
                f"Pendientes encontrados: "
                f"{total_pendientes}."
            )
        )

    # =========================================================
    # IDENTIFICAR QUÉ DEBE HACER COMPRAS
    # =========================================================
    def _obtener_motivo(
        self,
        linea,
        lineas_en_inventario,
    ):

        # ---------------------------------------------
        # 1. INFORMACIÓN INCOMPLETA
        # ---------------------------------------------
        if (
            not linea.proveedor_id
            or linea.precio_unitario is None
        ):
            return "Completar proveedor y precio"

        if linea.tipo_pago not in (
            "CONTADO",
            "CREDITO",
        ):
            return "Definir tipo de pago"

        # ---------------------------------------------
        # 2. CONTADO -> FINANZAS
        # ---------------------------------------------
        if linea.tipo_pago == "CONTADO":

            try:
                finance_line = linea.finance_line

            except Exception:

                return "Enviar a Finanzas"

            decision = str(
                getattr(
                    finance_line,
                    "decision",
                    "PENDIENTE",
                )
                or "PENDIENTE"
            ).upper()

            # Finanzas rechazó
            if decision == "RECHAZADO":

                return (
                    "Revisar rechazo y "
                    "reenviar a Finanzas"
                )

            aprobado = (
                bool(
                    getattr(
                        finance_line,
                        "pagado",
                        False,
                    )
                )
                or decision in (
                    "APROBADO",
                    "PROGRAMADO",
                )
            )

            # Está esperando a Finanzas.
            # No se alerta a Compras.
            if not aprobado:
                return None

        # ---------------------------------------------
        # 3. CRÉDITO -> GERENCIA
        # ---------------------------------------------
        elif linea.tipo_pago == "CREDITO":

            try:
                approval_line = (
                    linea.purchase_approval_line
                )

            except Exception:

                return "Enviar a Gerencia"

            estado = str(
                getattr(
                    approval_line,
                    "estado_aprobacion",
                    "PENDIENTE",
                )
                or "PENDIENTE"
            ).upper()

            if estado == "RECHAZADO":

                return (
                    "Revisar rechazo y "
                    "reenviar a Gerencia"
                )

            # Esperando decisión de Gerencia
            if estado != "APROBADO":
                return None

        # ---------------------------------------------
        # 4. YA APROBADO, PERO COMPRAS NO LO HA
        #    ENVIADO A INVENTARIO
        # ---------------------------------------------
        if linea.id not in lineas_en_inventario:

            return (
                "Aprobado: enviar a Inventario"
            )

        return None

    # =========================================================
    # CORREO TEXTO
    # =========================================================
    def _crear_texto(
        self,
        pendientes_por_paw,
        total_pendientes,
        dashboard_url,
    ):

        lineas = [
            "IMPETUS CONTROL",
            "",
            (
                f"Tienes {total_pendientes} "
                f"pendiente(s) que requieren "
                f"atención en Compras."
            ),
            "",
        ]

        for grupo in pendientes_por_paw:

            lineas.append(
                f"PAW #{grupo['paw_numero']} "
                f"- {grupo['paw_nombre']}"
            )

            for item in grupo["pendientes"]:

                lineas.append(
                    f"- {item['codigo']}: "
                    f"{item['motivo']}"
                )

            lineas.append(
                f"Revisar PAW: "
                f"{grupo['url']}"
            )

            lineas.append("")

        lineas.append(
            "Revisar módulo de Compras:"
        )

        lineas.append(
            dashboard_url
        )

        lineas.append("")

        lineas.append(
            "Este correo es una alerta automática. "
            "Las acciones deben realizarse "
            "dentro de Impetus Control."
        )

        return "\n".join(lineas)

    # =========================================================
    # CORREO HTML
    # =========================================================
    def _crear_html(
        self,
        pendientes_por_paw,
        total_pendientes,
        dashboard_url,
    ):

        bloques = []

        for grupo in pendientes_por_paw:

            filas = ""

            for item in grupo["pendientes"]:

                filas += f"""
                <tr>

                    <td style="
                        padding:10px;
                        border-bottom:1px solid #e5e7eb;
                        font-weight:700;
                    ">
                        {escape(str(item['codigo']))}
                    </td>

                    <td style="
                        padding:10px;
                        border-bottom:1px solid #e5e7eb;
                        color:#334155;
                    ">
                        {escape(str(item['motivo']))}
                    </td>

                </tr>
                """

            bloques.append(
                f"""
                <div style="
                    margin:18px 0;
                    padding:16px;
                    border:1px solid #e2e8f0;
                    border-radius:12px;
                    background:#ffffff;
                ">

                    <div style="
                        font-size:16px;
                        font-weight:800;
                        color:#0f172a;
                    ">
                        PAW #{escape(str(grupo['paw_numero']))}
                    </div>

                    <div style="
                        margin-top:4px;
                        color:#64748b;
                        font-size:13px;
                    ">
                        {escape(str(grupo['paw_nombre']))}
                    </div>

                    <table style="
                        width:100%;
                        border-collapse:collapse;
                        margin-top:12px;
                        font-size:13px;
                    ">

                        <thead>

                            <tr>

                                <th style="
                                    text-align:left;
                                    padding:8px 10px;
                                    background:#f8fafc;
                                ">
                                    Ítem
                                </th>

                                <th style="
                                    text-align:left;
                                    padding:8px 10px;
                                    background:#f8fafc;
                                ">
                                    Acción requerida
                                </th>

                            </tr>

                        </thead>

                        <tbody>

                            {filas}

                        </tbody>

                    </table>

                    <div style="
                        margin-top:14px;
                    ">

                        <a
                            href="{grupo['url']}"
                            style="
                                display:inline-block;
                                background:#2563eb;
                                color:#ffffff;
                                text-decoration:none;
                                padding:10px 16px;
                                border-radius:8px;
                                font-weight:800;
                            "
                        >
                            Revisar este PAW
                        </a>

                    </div>

                </div>
                """
            )

        return f"""
        <!doctype html>

        <html>

        <body style="
            margin:0;
            padding:0;
            background:#f1f5f9;
            font-family:Arial, Helvetica, sans-serif;
            color:#0f172a;
        ">

            <div style="
                max-width:760px;
                margin:0 auto;
                padding:24px;
            ">

                <div style="
                    background:#0f172a;
                    color:#ffffff;
                    padding:20px 24px;
                    border-radius:14px 14px 0 0;
                ">

                    <div style="
                        font-size:12px;
                        font-weight:700;
                        color:#cbd5e1;
                    ">
                        IMPETUS CONTROL
                    </div>

                    <div style="
                        font-size:24px;
                        font-weight:800;
                        margin-top:6px;
                    ">
                        Pendientes de Compras
                    </div>

                </div>

                <div style="
                    background:#ffffff;
                    padding:24px;
                    border-radius:0 0 14px 14px;
                ">

                    <p style="
                        font-size:15px;
                        line-height:1.6;
                        margin-top:0;
                    ">

                        Hay
                        <strong>
                            {total_pendientes}
                        </strong>
                        pendiente(s) que requieren
                        una acción del área de Compras.

                    </p>

                    {''.join(bloques)}

                    <div style="
                        text-align:center;
                        margin-top:24px;
                    ">

                        <a
                            href="{dashboard_url}"
                            style="
                                display:inline-block;
                                background:#16a34a;
                                color:#ffffff;
                                text-decoration:none;
                                padding:13px 20px;
                                border-radius:9px;
                                font-weight:800;
                            "
                        >
                            Revisar pendientes
                            en Impetus Control
                        </a>

                    </div>

                    <p style="
                        margin-top:24px;
                        color:#64748b;
                        font-size:12px;
                    ">

                        Este correo es una alerta
                        automática.

                        Las acciones deben realizarse
                        dentro de Impetus Control.

                    </p>

                </div>

            </div>

        </body>

        </html>
        """