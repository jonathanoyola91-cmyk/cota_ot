"""Conciliación explícita de reservas para PAW existentes; no contabiliza recepciones."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render

from auditoria.utils import registrar_movimiento
from compras_oil.models import PurchaseRequest
from .models import (
    InventoryReservation, InventoryStock, WorkshopDeliveryLine,
    ReceptionWarehouseTransfer, InventoryReceptionLine,
)


def faltante_reserva(requerida, entregada, consumida, liberada, reservada):
    # Consumo y entrega describen el mismo material: no se suman entre sí.
    return max(Decimal(requerida or 0) - max(Decimal(entregada or 0), Decimal(consumida or 0))
               - Decimal(liberada or 0) - Decimal(reservada or 0), Decimal("0"))


def _filas(compra, bloquear=False):
    lineas = compra.lineas.order_by("pk")
    if bloquear:
        lineas = lineas.select_for_update()
    resultado = []
    for linea in lineas:
        reservas = list(InventoryReservation.objects.filter(purchase_line=linea, purchase_request=compra))
        activa = sum((max(r.cantidad - r.cantidad_consumida, Decimal("0"))
                      for r in reservas if r.estado == InventoryReservation.Estado.ACTIVA), Decimal("0"))
        consumida = sum((r.cantidad_consumida for r in reservas), Decimal("0"))
        entregada = WorkshopDeliveryLine.objects.filter(purchase_line=linea).aggregate(
            total=Sum("cantidad_entregada"))["total"] or Decimal("0")
        liberada = ReceptionWarehouseTransfer.objects.filter(reception_line__purchase_line=linea).aggregate(
            total=Sum("cantidad"))["total"] or Decimal("0")
        stocks = InventoryStock.objects.filter(empresa="IMPETUS", codigo__iexact=linea.codigo.strip()).order_by("pk")
        if bloquear:
            stocks = stocks.select_for_update()
        # Códigos duplicados requieren revisión de catálogo antes de reservar.
        stocks = list(stocks[:2])
        stock = stocks[0] if len(stocks) == 1 else None
        disponible = max(stock.cantidad_disponible, Decimal("0")) if stock else Decimal("0")
        recibida = InventoryReceptionLine.objects.filter(purchase_line=linea).aggregate(
            total=Sum("cantidad_recibida"))["total"] or Decimal("0")
        faltante = faltante_reserva(linea.cantidad_requerida, entregada, consumida, liberada, activa)
        resultado.append(dict(linea=linea, stock=stock, reservada=activa,
            entregada=max(entregada, consumida), liberada=liberada, recibida=recibida,
            faltante=faltante, disponible=disponible, maximo=min(disponible, faltante),
            catalogo_ambiguo=len(stocks) > 1))
    return resultado


def revisar_reservas(request, compra):
    # Llamada exclusivamente desde revision_bom_detail, protegida por Inventario.
    if request.method == "POST":
        try:
            with transaction.atomic():
                compra = PurchaseRequest.objects.select_for_update().get(pk=compra.pk)
                if not compra.revision_reservas_pendiente:
                    messages.info(request, "Esta revisión ya fue confirmada.")
                    return redirect("inventario:revision_bom_detail", pk=compra.pk)
                if compra.estado == "CERRADA" or compra.bom.workorder.paw.estado_operativo in ("FACTURADO", "RADICADO"):
                    raise ValueError("La solicitud está cerrada o facturada.")
                filas = _filas(compra, bloquear=True)
                operaciones, por_stock = [], {}
                for fila in filas:
                    raw = request.POST.get(f"reservar_{fila['linea'].pk}", "0") or "0"
                    try:
                        cantidad = Decimal(raw.replace(",", "."))
                    except InvalidOperation:
                        raise ValueError("Ingrese una cantidad válida.")
                    if not cantidad.is_finite() or cantidad < 0 or cantidad.as_tuple().exponent < -3:
                        raise ValueError("Use cantidades positivas o cero, con hasta tres decimales.")
                    if cantidad > fila["maximo"]:
                        raise ValueError(f"{fila['linea'].codigo}: la reserva adicional supera el faltante o el disponible actual.")
                    if cantidad:
                        stock = fila["stock"]
                        por_stock[stock.pk] = por_stock.get(stock.pk, Decimal("0")) + cantidad
                        if por_stock[stock.pk] > stock.cantidad_disponible:
                            raise ValueError(f"{stock.codigo}: varias líneas solicitan más que la existencia disponible.")
                        operaciones.append((fila, cantidad))
                for fila, cantidad in operaciones:
                    stock = fila["stock"]
                    InventoryReservation.objects.create(
                        stock=stock, cantidad=cantidad, purchase_request=compra,
                        purchase_line=fila["linea"], creado_por=request.user,
                        observacion=f"Conciliación de reserva PAW {compra.paw_numero}",
                    )
                for stock_id, cantidad in por_stock.items():
                    stock = InventoryStock.objects.get(pk=stock_id)
                    stock.cantidad_reservada += cantidad
                    stock.save(update_fields=["cantidad_reservada", "actualizado_en"])
                adicionales = {f["linea"].pk: c for f, c in operaciones}
                sin_cubrir = any(f["faltante"] > adicionales.get(f["linea"].pk, 0) for f in filas)
                compra.revision_reservas_pendiente = sin_cubrir
                # Conserva el marcador de la revisión incremental original.
                compra.save(update_fields=["revision_reservas_pendiente", "actualizado_en"])
                registrar_movimiento(
                    request=request, paw_numero=compra.paw_numero, modulo="INVENTARIO",
                    accion="Reservas de PAW conciliadas",
                    descripcion="Reservas adicionales desde stock disponible; sin modificar compras, recepciones ni entregas.",
                    objeto=compra,
                    datos_nuevos={"reservas": [{"linea": f["linea"].pk, "cantidad": str(c)} for f, c in operaciones]},
                )
            messages.success(request, "Reservas guardadas. Quedan líneas pendientes de cubrir." if sin_cubrir else "Reservas conciliadas correctamente.")
            return redirect("inventario:revision_bom_detail", pk=compra.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "inventario/revision_reservas.html", {"compra": compra, "filas": _filas(compra)})
