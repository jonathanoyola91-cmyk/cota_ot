from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from paw_app.models import Paw
from .models import Factura


@login_required
def dashboard_facturacion(request):
    facturas = Factura.objects.select_related("paw").order_by("-actualizado_en")

    return render(request, "facturacion/dashboard.html", {
        "facturas": facturas
    })


@login_required
def crear_desde_paw(request, paw_id):
    paw = get_object_or_404(Paw, id=paw_id)

    factura, created = Factura.objects.get_or_create(paw=paw)

    paw.estado_operativo = "EN_FACTURACION"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "PAW enviado a facturación.")
    return redirect("facturacion:detalle", pk=factura.pk)

@login_required
def crear_desde_paw(request, paw_id):
    paw = get_object_or_404(Paw, id=paw_id)

    if paw.estado_operativo != "PRODUCTO_OK":
        messages.error(request, "No puede enviar a facturación hasta que el producto esté OK.")
        return redirect("paw_detail", paw_id=paw.id)

    factura, created = Factura.objects.get_or_create(paw=paw)

    paw.estado_operativo = "EN_FACTURACION"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "PAW enviado a facturación.")
    return redirect("facturacion:detalle", pk=factura.pk)


@login_required
def detalle_factura(request, pk):
    factura = get_object_or_404(
        Factura.objects.select_related("paw"),
        pk=pk
    )

    from .forms import FacturaForm

    if request.method == "POST":
        form = FacturaForm(request.POST, instance=factura)

        if form.is_valid():
            factura = form.save()

            if factura.estado == "facturado":
                factura.paw.estado_operativo = "FACTURADO"
            elif factura.estado == "radicacion":
                factura.paw.estado_operativo = "RADICADO"
            elif factura.estado == "vencida":
                factura.paw.estado_operativo = "RADICADO"

            factura.paw.save(update_fields=["estado_operativo"])

            messages.success(request, "Factura actualizada.")
            return redirect("facturacion:detalle", pk=factura.pk)

    else:
        form = FacturaForm(instance=factura)

    return render(request, "facturacion/detalle.html", {
        "factura": factura,
        "form": form,
    })

@login_required
def radicar_factura(request, pk):
    factura = get_object_or_404(Factura, pk=pk)

    factura.fecha_radicacion = timezone.now().date()
    factura.estado = "radicacion"
    factura.save()

    paw = factura.paw
    paw.estado_operativo = "RADICADO"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Factura radicada correctamente.")
    return redirect("facturacion:detalle", pk=factura.pk)