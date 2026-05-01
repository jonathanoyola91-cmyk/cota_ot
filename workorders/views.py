from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import WorkOrder
from paw_app.models import Paw


@login_required
def ot_list(request):
    ots = WorkOrder.objects.select_related("paw", "creado_por").order_by("-creado_en")
    return render(request, "workorders/ot_list.html", {"ots": ots})


@login_required
def ot_detail(request, numero):
    ot = get_object_or_404(
        WorkOrder.objects.select_related("paw", "creado_por", "asignado_a", "asignado_grupo"),
        numero=numero
    )
    return render(request, "workorders/ot_detail.html", {"ot": ot})


@login_required
def crear_ot_desde_paw(request, paw_id):
    paw = get_object_or_404(Paw, id=paw_id)

    ot = WorkOrder.objects.create(
        paw=paw,
        titulo=f"OT PAW {paw.numero_paw} - {paw.nombre_paw}",
        descripcion=f"Orden de trabajo creada desde PAW {paw.numero_paw}",
        cliente=paw.cliente,
        ubicacion=paw.campo,
        creado_por=request.user,
        prioridad=WorkOrder.Priority.MEDIA,
        estado=WorkOrder.Status.NUEVA,
        visibilidad=WorkOrder.Visibility.RESTRINGIDA,
    )

    paw.estado_operativo = "OT_CREADA"
    paw.save(update_fields=["estado_operativo"])

    return redirect("ot_detail", numero=ot.numero)


@login_required
def confirmar_ensamble_ok(request, numero):
    ot = get_object_or_404(WorkOrder, numero=numero)

    if ot.ensamble_ok:
        messages.info(request, "Este ensamble ya había sido confirmado.")
        return redirect(request.META.get("HTTP_REFERER", "ot_detail"), numero=ot.numero)

    ot.ensamble_ok = True
    ot.fecha_ensamble_ok = timezone.now()
    ot.etapa_taller = WorkOrder.EtapaTaller.TERMINADO
    ot.estado = WorkOrder.Status.TERMINADA
    ot.terminado_en = timezone.now()
    ot.save(update_fields=[
        "ensamble_ok",
        "fecha_ensamble_ok",
        "etapa_taller",
        "estado",
        "terminado_en",
        "actualizado_en",
    ])

    if ot.paw:
        ot.paw.estado_operativo = "ENSAMBLE_OK"
        ot.paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Ensamble confirmado correctamente.")
    return redirect(request.META.get("HTTP_REFERER", "ot_detail"), numero=ot.numero)