from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Paw
from quotes.models import Quotation
from django.contrib import messages


@login_required
def paw_list(request):
    paws = Paw.objects.select_related("cotizacion", "creado_por").order_by("-creado_en")
    return render(request, "paw_app/paw_list.html", {"paws": paws})


@login_required
def paw_detail(request, paw_id):
    paw = get_object_or_404(
        Paw.objects.select_related("cotizacion", "creado_por"),
        id=paw_id
    )
    return render(request, "paw_app/paw_detail.html", {"paw": paw})


@login_required
def crear_paw(request, cotizacion_id):
    cotizacion = get_object_or_404(Quotation, id=cotizacion_id)

    paw_existente = Paw.objects.filter(cotizacion=cotizacion).first()

    if paw_existente:
        messages.warning(request, "Esta cotización ya tiene un PAW generado.")
        return redirect("paw_detail", paw_id=paw_existente.id)

    if request.method == "POST":
        paw = Paw.objects.create(
            cotizacion=cotizacion,
            creado_por=request.user
        )

        messages.success(request, "PAW creado correctamente.")
        return redirect("paw_detail", paw_id=paw.id)

    return render(request, "paw_app/crear_paw.html", {
        "cotizacion": cotizacion
    })

def marcar_producto_ok(request, paw_id):
    paw = get_object_or_404(Paw, id=paw_id)

    if paw.estado_operativo != "ENTREGADO_TALLER":
        messages.error(request, "No puede marcar producto OK hasta registrar ensamble.")
        return redirect("paw_detail", paw_id=paw.id)

    paw.estado_operativo = "PRODUCTO_OK"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Producto marcado como OK.")
    return redirect("paw_detail", paw_id=paw.id)

def registrar_ensamble(request, paw_id):
    paw = get_object_or_404(Paw, id=paw_id)
    paw.estado_operativo = "ENTREGADO_TALLER"
    paw.save(update_fields=["estado_operativo"])
    return redirect("paw_detail", paw_id=paw.id)

def registrar_ensamble(request, paw_id):
    paw = get_object_or_404(Paw, id=paw_id)

    if paw.estado_operativo != "MATERIAL_RECIBIDO":
        messages.error(request, "No puede registrar ensamble hasta que el material esté recibido.")
        return redirect("paw_detail", paw_id=paw.id)

    paw.estado_operativo = "ENTREGADO_TALLER"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Ensamble registrado correctamente.")
    return redirect("paw_detail", paw_id=paw.id)