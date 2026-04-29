from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from workorders.models import WorkOrder
from .models import Bom, BomItem, BomTemplate
from compras_oil.models import PurchaseRequest, PurchaseLine


@login_required
def crear_bom_desde_ot(request, ot_numero):
    ot = get_object_or_404(WorkOrder, numero=ot_numero)

    if hasattr(ot, "bom"):
        return redirect("bom_detail", bom_id=ot.bom.id)

    templates = BomTemplate.objects.filter(activo=True).order_by("nombre")

    if request.method == "POST":
        template_id = request.POST.get("template")
        comentarios = request.POST.get("comentarios", "")

        template = None
        if template_id:
            template = get_object_or_404(BomTemplate, id=template_id)

        bom = Bom.objects.create(
            workorder=ot,
            template=template,
            comentarios=comentarios
            
        )

        if ot.paw:
            paw = ot.paw
            paw.estado_operativo = "BOM_CREADO"
            paw.save(update_fields=["estado_operativo"])

        if template:
            for item in template.items.all():
                BomItem.objects.create(
                    bom=bom,
                    plano=item.plano,
                    codigo=item.codigo,
                    descripcion=item.descripcion,
                    unidad=item.unidad,
                    cantidad_estandar=item.cantidad_estandar,
                    cantidad_solicitada=item.cantidad_estandar,
                    observaciones=item.observaciones,
                )

        return redirect("bom_detail", bom_id=bom.id)

    return render(request, "bom/crear_bom.html", {
        "ot": ot,
        "templates": templates,
    })


@login_required
def bom_detail(request, bom_id):
    bom = get_object_or_404(
        Bom.objects.select_related("workorder", "template"),
        id=bom_id
    )
    return render(request, "bom/bom_detail.html", {"bom": bom})


def agregar_item_bom(request, bom_id):
    bom = get_object_or_404(Bom, id=bom_id)

    if request.method == "POST":
        BomItem.objects.create(
            bom=bom,
            plano=request.POST.get("plano", ""),
            codigo=request.POST.get("codigo", ""),
            descripcion=request.POST.get("descripcion", ""),
            unidad=request.POST.get("unidad", ""),
            cantidad_estandar=request.POST.get("cantidad_estandar") or 0,
            cantidad_solicitada=request.POST.get("cantidad_solicitada") or 0,
            observaciones=request.POST.get("observaciones", ""),
        )
        return redirect("agregar_item_bom", bom_id=bom.id)

    return render(request, "bom/agregar_item_bom.html", {"bom": bom})

def editar_item_bom(request, item_id):
    item = get_object_or_404(BomItem, id=item_id)
    bom = item.bom

    if request.method == "POST":
        item.plano = request.POST.get("plano", "")
        item.codigo = request.POST.get("codigo", "")
        item.descripcion = request.POST.get("descripcion", "")
        item.unidad = request.POST.get("unidad", "")
        item.cantidad_estandar = request.POST.get("cantidad_estandar") or 0
        item.cantidad_solicitada = request.POST.get("cantidad_solicitada") or 0
        item.observaciones = request.POST.get("observaciones", "")
        item.save()

        return redirect("agregar_item_bom", bom_id=bom.id)

    return render(request, "bom/editar_item_bom.html", {
        "item": item,
        "bom": bom,
    })


def eliminar_item_bom(request, item_id):
    item = get_object_or_404(BomItem, id=item_id)
    bom = item.bom

    if request.method == "POST":
        item.delete()
        return redirect("agregar_item_bom", bom_id=bom.id)

    return render(request, "bom/eliminar_item_bom.html", {
        "item": item,
        "bom": bom,
    })

def enviar_bom_compras(request, bom_id):
    bom = get_object_or_404(Bom.objects.prefetch_related("items"), id=bom_id)

    if request.method == "POST":

        bom.marcar_solicitud()

        compra, created = PurchaseRequest.objects.get_or_create(
            bom=bom,
            defaults={
                "estado": "BORRADOR",
                "creado_por": request.user,
                "paw_numero": bom.workorder.paw.numero_paw if bom.workorder.paw else "",
                "paw_nombre": bom.workorder.paw.nombre_paw if bom.workorder.paw else "",
            }
        )

        if bom.workorder.paw:
            paw = bom.workorder.paw
            paw.estado_operativo = "EN_COMPRAS"
            paw.save(update_fields=["estado_operativo"])

        if created:
            for item in bom.items.all():
                PurchaseLine.objects.create(
                    request=compra,
                    bom_item=item,
                    descripcion=item.descripcion,
                )

        return redirect("compras_oil:paw_detail", pk=compra.pk)

    return render(request, "bom/enviar_bom_compras.html", {"bom": bom})