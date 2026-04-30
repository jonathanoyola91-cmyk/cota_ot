from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from core.roles import tiene_rol
from paw_app.models import Paw
from .models import Factura
from .forms import FacturaForm


def _sumar_valores_facturas(queryset):
    """
    Suma valores financieros usando las propiedades del modelo Factura:
    - iva
    - total_con_iva
    """
    subtotal = 0
    iva = 0
    total = 0

    for factura in queryset:
        if factura.precio:
            subtotal += factura.precio
            iva += factura.iva
            total += factura.total_con_iva

    return subtotal, iva, total


def _analisis_empresa(facturas, prefijo):
    """
    Calcula análisis financiero por empresa según prefijo de número de factura.
    Ejemplos:
    - OG  -> Oil Gas
    - IMP -> Impetus
    """
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)
    inicio_anio = hoy.replace(month=1, day=1)

    # Cuatrimestres calendario:
    # Ene-Abr, May-Ago, Sep-Dic
    if hoy.month <= 4:
        inicio_cuatrimestre = hoy.replace(month=1, day=1)
    elif hoy.month <= 8:
        inicio_cuatrimestre = hoy.replace(month=5, day=1)
    else:
        inicio_cuatrimestre = hoy.replace(month=9, day=1)

    qs_empresa = facturas.filter(numero_factura__icontains=prefijo)

    qs_mes = qs_empresa.filter(fecha_radicacion__gte=inicio_mes)
    qs_cuatrimestre = qs_empresa.filter(fecha_radicacion__gte=inicio_cuatrimestre)
    qs_anio = qs_empresa.filter(fecha_radicacion__gte=inicio_anio)

    subtotal_mes, iva_mes, total_mes = _sumar_valores_facturas(qs_mes)
    subtotal_cuatrimestre, iva_cuatrimestre, total_cuatrimestre = _sumar_valores_facturas(qs_cuatrimestre)
    subtotal_anio, iva_anio, total_anio = _sumar_valores_facturas(qs_anio)

    return {
        "subtotal_mes": subtotal_mes,
        "iva_mes": iva_mes,
        "total_mes": total_mes,
        "subtotal_cuatrimestre": subtotal_cuatrimestre,
        "iva_cuatrimestre": iva_cuatrimestre,
        "total_cuatrimestre": total_cuatrimestre,
        "subtotal_anio": subtotal_anio,
        "iva_anio": iva_anio,
        "total_anio": total_anio,
        "cantidad": qs_empresa.count(),
    }


@login_required
def dashboard_facturacion(request):
    if not tiene_rol(request.user, ["COMERCIAL", "FINANZAS", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes acceso a Facturación.")
        return redirect("/dashboard/")

    facturas = Factura.objects.select_related("paw").order_by("-actualizado_en")

    analisis_og = _analisis_empresa(facturas, "OG")
    analisis_imp = _analisis_empresa(facturas, "IMP")

    return render(request, "facturacion/dashboard.html", {
        "facturas": facturas,
        "analisis_og": analisis_og,
        "analisis_imp": analisis_imp,
    })


@login_required
def crear_desde_paw(request, paw_id):
    if not tiene_rol(request.user, ["COMERCIAL", "GERENTE", "ADMIN"]):
        messages.error(request, "Solo Comercial puede enviar PAW a facturación.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if paw.estado_operativo != "PRODUCTO_OK":
        messages.error(
            request,
            "No puede enviar a facturación hasta que el producto esté OK."
        )
        return redirect("paw_detail", paw_id=paw.id)

    factura, created = Factura.objects.get_or_create(paw=paw)

    paw.estado_operativo = "EN_FACTURACION"
    paw.save(update_fields=["estado_operativo"])

    if created:
        messages.success(request, "PAW enviado a facturación correctamente.")
    else:
        messages.info(request, "Este PAW ya tenía una factura asociada.")

    return redirect("facturacion:detalle", pk=factura.pk)


@login_required
def detalle_factura(request, pk):
    if not tiene_rol(request.user, ["COMERCIAL", "FINANZAS", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes permiso para ver esta factura.")
        return redirect("/dashboard/")

    factura = get_object_or_404(
        Factura.objects.select_related("paw"),
        pk=pk
    )

    if request.method == "POST":
        form = FacturaForm(request.POST, instance=factura)

        if form.is_valid():
            factura = form.save(commit=False)

            if factura.estado == "facturado":
                factura.paw.estado_operativo = "FACTURADO"
            elif factura.estado == "radicacion":
                factura.paw.estado_operativo = "RADICADO"
            elif factura.estado == "vencida":
                factura.paw.estado_operativo = "RADICADO"
            elif factura.estado == "pagada":
                factura.paw.estado_operativo = "FACTURADO"
            else:
                factura.paw.estado_operativo = "EN_FACTURACION"

            factura.save()
            factura.paw.save(update_fields=["estado_operativo"])

            messages.success(request, "Factura actualizada correctamente.")
            return redirect("facturacion:detalle", pk=factura.pk)
    else:
        form = FacturaForm(instance=factura)

    puede_radicar = tiene_rol(request.user, ["FINANZAS", "GERENTE", "ADMIN"])
    puede_editar = tiene_rol(request.user, ["COMERCIAL", "FINANZAS", "GERENTE", "ADMIN"])

    return render(request, "facturacion/detalle.html", {
        "factura": factura,
        "form": form,
        "puede_radicar": puede_radicar,
        "puede_editar": puede_editar,
    })


@login_required
def radicar_factura(request, pk):
    if not tiene_rol(request.user, ["FINANZAS", "GERENTE", "ADMIN"]):
        messages.error(request, "Solo Finanzas puede radicar facturas.")
        return redirect("facturacion:detalle", pk=pk)

    factura = get_object_or_404(Factura, pk=pk)

    factura.fecha_radicacion = timezone.now().date()
    factura.estado = "radicacion"
    factura.save(update_fields=["fecha_radicacion", "estado", "actualizado_en"])

    paw = factura.paw
    paw.estado_operativo = "RADICADO"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Factura radicada correctamente.")
    return redirect("facturacion:detalle", pk=factura.pk)


@login_required
def marcar_pagada(request, pk):
    if not tiene_rol(request.user, ["FINANZAS", "GERENTE", "ADMIN"]):
        messages.error(request, "Solo Finanzas puede marcar facturas como pagadas.")
        return redirect("facturacion:detalle", pk=pk)

    factura = get_object_or_404(Factura, pk=pk)

    factura.estado = "pagada"
    factura.fecha_pago = timezone.now().date()
    factura.save(update_fields=["estado", "fecha_pago", "actualizado_en"])

    messages.success(request, "Factura marcada como pagada correctamente.")
    return redirect("facturacion:detalle", pk=factura.pk)
