from collections import defaultdict
from datetime import date, datetime, timedelta, time
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from workorders.models import WorkOrder
from compras_oil.models import PurchaseRequest
from inventario.models import WorkshopDelivery
from paw_app.models import Paw
from .forms_horas import AsignarTecnicosTallerForm, IniciarEnsambleForm, JornadaTallerForm
from .models import CamaraTaller, EnsambleTaller, JornadaTaller, OrdenMecanizadoEje


def optimizar_foto_metrologia(archivo, max_lado=1920, calidad=82):
    """Reduce fotografías de evidencia antes de almacenarlas.

    Corrige la orientación EXIF, limita el lado mayor y convierte a JPEG
    optimizado. Si Pillow no puede procesar el archivo, lanza ValueError para
    que la vista informe al usuario sin perder las mediciones ya diligenciadas.
    """
    try:
        archivo.seek(0)
        with Image.open(archivo) as img:
            img = ImageOps.exif_transpose(img)

            if img.mode not in ("RGB", "L"):
                # Las evidencias son fotografías; un fondo blanco evita fondos
                # negros si excepcionalmente llega una imagen con transparencia.
                if "A" in img.getbands():
                    fondo = Image.new("RGB", img.size, "white")
                    alpha = img.getchannel("A")
                    fondo.paste(img.convert("RGB"), mask=alpha)
                    img = fondo
                else:
                    img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")

            img.thumbnail((max_lado, max_lado), Image.Resampling.LANCZOS)

            salida = BytesIO()
            img.save(
                salida,
                format="JPEG",
                quality=calidad,
                optimize=True,
                progressive=True,
            )
    except Exception as exc:
        raise ValueError("No fue posible procesar la fotografía seleccionada.") from exc

    nombre_base = Path(getattr(archivo, "name", "evidencia")).stem
    nombre = f"{nombre_base[:80] or 'evidencia'}.jpg"
    return ContentFile(salida.getvalue(), name=nombre)


def obtener_bom_seguro(ot):
    try:
        return ot.bom
    except Exception:
        return None


def puede_editar_taller(user):
    return tiene_rol(user, ["TALLER", "ADMIN"])


def calcular_progreso_entrega(entrega):
    """Calcula el avance con la cantidad neta que todavía exige el PAW.

    La cantidad original deja de ser la referencia cuando Inventario libera a
    bodega o cancela justificadamente un saldo. Usar la cantidad neta evita que
    Taller vea entregas completas como si todavía estuvieran parciales.
    """
    total_requerido = Decimal("0")
    total_entregado = Decimal("0")
    total_lineas = 0
    lineas_entregadas = 0

    for linea in entrega.lineas.all():
        requerido = Decimal(linea.cantidad_requerida_neta or 0)
        entregado = Decimal(linea.cantidad_entregada or 0)

        if requerido <= 0:
            continue

        total_requerido += requerido
        total_entregado += min(entregado, requerido)
        total_lineas += 1

        if entregado >= requerido:
            lineas_entregadas += 1

    porcentaje = 0
    if total_requerido > 0:
        porcentaje = min(round((total_entregado / total_requerido) * 100), 100)

    return {
        "total_requerido": total_requerido,
        "total_entregado": total_entregado,
        "total_lineas": total_lineas,
        "lineas_entregadas": lineas_entregadas,
        "porcentaje": porcentaje,
        "completa": total_requerido > 0 and total_entregado >= total_requerido,
    }


@login_required
def dashboard(request):
    estados_paw_fuera_operacion = [
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    ]

    # Una OT cuyo PAW ya salió de operación no debe seguir apareciendo