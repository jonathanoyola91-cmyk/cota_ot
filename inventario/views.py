from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from decimal import Decimal

from .models import InventoryReception, InventoryReceptionLine, WorkshopDelivery
from django.http import HttpResponse

@login_required
def entrega_taller_pdf(request, pk):
    entrega = get_object_or_404(
        WorkshopDelivery.objects.prefetch_related("lineas"),
        pk=pk
    )

    html = f"""
    <h2>Entrega a Taller - PAW {entrega.purchase_request.paw_numero}</h2>
    <p>{entrega.purchase_request.paw_nombre}</p>
    <table border="1" cellpadding="5">
        <tr>
            <th>Código</th>
            <th>Descripción</th>
            <th>Cantidad</th>
        </tr>
    """

    for l in entrega.lineas.all():
        html += f"""
        <tr>
            <td>{l.codigo}</td>
            <td>{l.descripcion}</td>
            <td>{l.cantidad_entregada or 0}</td>
        </tr>
        """

    html += "</table>"

    return HttpResponse(html)


@login_required
def inventario_dashboard(request):
    recepciones = (
        InventoryReception.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas")
        .order_by("-actualizado_en")
    )

    entregas = (
        WorkshopDelivery.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas")
        .order_by("-actualizado_en")
    )

    return render(request, "inventario/dashboard.html", {
        "recepciones": recepciones,
        "entregas": entregas,
        "total_recepciones": recepciones.count(),
        "total_entregas": entregas.count(),
        "lineas_pendientes": InventoryReceptionLine.objects.filter(estado="PENDIENTE").count(),
        "lineas_listas": InventoryReceptionLine.objects.filter(estado="LISTO").count(),
    })


@login_required
def recepcion_detail(request, pk):
    recepcion = get_object_or_404(
        InventoryReception.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas__purchase_line"),
        pk=pk
    )

    if request.method == "POST":
        for linea in recepcion.lineas.all():
            cantidad = request.POST.get(f"cantidad_recibida_{linea.id}") or 0
            fecha = request.POST.get(f"fecha_llegada_{linea.id}") or None
            observacion = request.POST.get(f"observacion_{linea.id}") or ""
            cantidad = request.POST.get(f"cantidad_recibida_{linea.id}") or "0"
            cantidad = Decimal(cantidad.replace(",", "."))

            linea.cantidad_recibida = cantidad

            linea.cantidad_recibida = cantidad
            linea.fecha_llegada = fecha
            linea.observacion_inventario = observacion

            if Decimal(linea.cantidad_recibida or 0) >= Decimal(linea.cantidad_esperada or 0):
                linea.estado = "LISTO"
            else:
                linea.estado = "PENDIENTE"

            linea.save()

        if not recepcion.lineas.filter(estado="PENDIENTE").exists():
            try:
                paw = recepcion.purchase_request.bom.workorder.paw
                paw.estado_operativo = "MATERIAL_RECIBIDO"
                paw.save(update_fields=["estado_operativo"])
            except Exception:
                pass

        messages.success(request, "Recepción de inventario actualizada correctamente.")
        return redirect("inventario:recepcion_detail", pk=recepcion.pk)

    return render(request, "inventario/recepcion_detail.html", {
        "recepcion": recepcion
    })


@login_required
def entrega_taller_detail(request, pk):
    entrega = get_object_or_404(
        WorkshopDelivery.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas"),
        pk=pk
    )

    if request.method == "POST":
        entrega.comentarios = request.POST.get("comentarios", "")
        entrega.save(update_fields=["comentarios"])

        messages.success(request, "Entrega a taller actualizada correctamente.")
        return redirect("inventario:entrega_taller_detail", pk=entrega.pk)

    return render(request, "inventario/entrega_taller_detail.html", {
        "entrega": entrega
    })