from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from workorders.models import WorkOrder
from .models import Bom, BomItem, BomTemplate
from compras_oil.models import PurchaseRequest, PurchaseLine

from django.http import JsonResponse
from django.db.models import Q

from item_oil_gas.models import ItemImpetus
from auditoria.utils import registrar_movimiento



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
            # Crear el BOM solo puede avanzar estados iniciales; nunca debe hacer retroceder el PAW.
            if paw.estado_operativo in {"PAW_CREADO", "OT_CREADA"}:
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
        Bom.objects.select_related("workorder", "template").prefetch_related("items"),
        id=bom_id
    )

    if request.method == "POST" and bom.estado == Bom.Estado.BORRADOR:
        for item in bom.items.all():
            cantidad = request.POST.get(f"cantidad_solicitada_{item.id}")
            observacion = request.POST.get(f"observaciones_{item.id}", "")

            if cantidad is not None:
                item.cantidad_solicitada = cantidad or 0
                item.observaciones = observacion
                item.save(update_fields=["cantidad_solicitada", "observaciones"])

        return redirect("bom_detail", bom_id=bom.id)

    return render(request, "bom/bom_detail.html", {"bom": bom})

@login_required
def buscar_items_catalogo(request, bom_id):
    """
    Busca items exclusivamente en el catálogo operativo IMPETUS.
    El catálogo del BOM no depende de la empresa de la cotización.
    """

    # Validamos que el BOM exista.
    # No necesitamos revisar si la cotización es IMPETUS u OIL_GAS,
    # porque operaciones siempre trabaja con el catálogo IMPETUS.
    get_object_or_404(Bom, id=bom_id)

    q = request.GET.get("q", "").strip()

    queryset = ItemImpetus.objects.filter(activo=True)

    if q:
        queryset = queryset.filter(
            Q(codigo__icontains=q) |
            Q(descripcion__icontains=q)
        )

    queryset = queryset.order_by("codigo")[:50]

    items = []

    for item in queryset:
        items.append({
            "id": item.id,
            "codigo": item.codigo,
            "descripcion": item.descripcion,
            "unidad": item.unidad_medida or "",
            "clasificacion": item.clasificacion or "",
            "grupo_inventario": item.grupo_inventario or "",
        })

    return JsonResponse({
        "catalogo": "IMPETUS",
        "items": items,
    })


@login_required
def agregar_item_bom(request, bom_id):

    bom = get_object_or_404(
        Bom.objects.select_related(
            "workorder",
            "workorder__paw",
            "workorder__paw__cotizacion"
        ),
        id=bom_id
    )

    # El BOM siempre trabaja con el catálogo operativo IMPETUS.
    catalogo_nombre = "IMPETUS"

    if request.method == "POST":

        catalogo_id = request.POST.get("catalogo_id")

        # ==========================================
        # ITEM SELECCIONADO DESDE CATÁLOGO IMPETUS
        # ==========================================

        if catalogo_id:

            item_catalogo = get_object_or_404(
                ItemImpetus,
                id=catalogo_id,
                activo=True
            )

            nuevo_item = BomItem.objects.create(
                bom=bom,
                plano=request.POST.get("plano", "").strip(),
                codigo=item_catalogo.codigo,
                descripcion=item_catalogo.descripcion,
                unidad=item_catalogo.unidad_medida or "",
                clasificacion=item_catalogo.clasificacion or "",
                grupo_inventario=item_catalogo.grupo_inventario or "",
                cantidad_estandar=request.POST.get("cantidad_estandar") or 0,
                cantidad_solicitada=request.POST.get("cantidad_solicitada") or 0,
                observaciones=request.POST.get("observaciones", "").strip(),
            )

        # ==========================================
        # ITEM MANUAL
        # ==========================================

        else:

            nuevo_item = BomItem.objects.create(
                bom=bom,
                plano=request.POST.get("plano", "").strip(),
                codigo=request.POST.get("codigo", "").strip(),
                descripcion=request.POST.get("descripcion", "").strip(),
                unidad=request.POST.get("unidad", "").strip(),
                clasificacion=request.POST.get("clasificacion", "").strip(),
                grupo_inventario=request.POST.get("grupo_inventario", "").strip(),
                cantidad_estandar=request.POST.get("cantidad_estandar") or 0,
                cantidad_solicitada=request.POST.get("cantidad_solicitada") or 0,
                observaciones=request.POST.get("observaciones", "").strip(),
            )

        # ==========================================
        # SINCRONIZACIÓN CON COMPRAS
        # ==========================================

        compra = PurchaseRequest.objects.filter(bom=bom).first()

        if compra:
            PurchaseLine.objects.get_or_create(
                request=compra,
                bom_item=nuevo_item,
                defaults={
                    "codigo": nuevo_item.codigo,
                    "descripcion": nuevo_item.descripcion,
                    "cantidad_requerida": nuevo_item.cantidad_solicitada,
                }
            )

        return redirect(
            "agregar_item_bom",
            bom_id=bom.id
        )

    return render(
        request,
        "bom/agregar_item_bom.html",
        {
            "bom": bom,
            "catalogo_nombre": catalogo_nombre,
        }
    )


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

@login_required
def enviar_bom_compras(request, bom_id):
    """
    Envía o reenvía el BOM a Inventario.

    Si la PAW ya había sido revisada:
    - sincroniza nuevas líneas del BOM con PurchaseLine;
    - conserva proveedor, precio, tipo de pago y aprobaciones de líneas existentes;
    - vuelve a abrir la revisión de Inventario;
    - no elimina el histórico/comercial ya trabajado por Compras.
    """
    bom = get_object_or_404(
        Bom.objects.select_related("workorder", "workorder__paw").prefetch_related("items"),
        id=bom_id,
    )

    if request.method == "POST":
        bom.marcar_solicitud()
        paw = bom.workorder.paw if bom.workorder else None

        compra, creada = PurchaseRequest.objects.get_or_create(
            bom=bom,
            defaults={
                "estado": PurchaseRequest.Estado.BORRADOR,
                "creado_por": request.user,
                "paw_numero": paw.numero_paw if paw else "",
                "paw_nombre": paw.nombre_paw if paw else "",
            },
        )

        # Guardamos si ya había sido revisada para identificar un REENVÍO.
        ya_estaba_revisada = bool(compra.inventario_revisado_en)

        campos_compra = []
        if paw:
            if compra.paw_numero != paw.numero_paw:
                compra.paw_numero = paw.numero_paw
                campos_compra.append("paw_numero")
            if compra.paw_nombre != paw.nombre_paw:
                compra.paw_nombre = paw.nombre_paw
                campos_compra.append("paw_nombre")

        items_bom = list(bom.items.all())
        ids_bom_actuales = [item.id for item in items_bom]

        # Si nunca había sido revisada, podemos limpiar líneas que ya no estén en el BOM.
        # Si ya pasó por Inventario/Compras, NO borramos líneas históricas para no perder
        # proveedor, precio, aprobaciones u otra gestión comercial.
        if not ya_estaba_revisada:
            PurchaseLine.objects.filter(request=compra).exclude(
                bom_item_id__in=ids_bom_actuales
            ).delete()

        lineas_nuevas = 0
        lineas_actualizadas = 0

        # Siempre sincronizar el BOM, incluso si ya fue revisado anteriormente.
        for item in items_bom:
            linea, linea_creada = PurchaseLine.objects.get_or_create(
                request=compra,
                bom_item=item,
                defaults={
                    "codigo": item.codigo,
                    "descripcion": item.descripcion,
                    "cantidad_requerida": item.cantidad_solicitada,
                    "cantidad_disponible": 0,
                },
            )

            if linea_creada:
                lineas_nuevas += 1
            else:
                lineas_actualizadas += 1

            # Datos técnicos siempre se refrescan desde el BOM.
            # NO tocar proveedor, precio, tipo_pago, porcentaje ni observaciones de Compras.
            linea.plano = item.plano or ""
            linea.codigo = item.codigo or ""
            linea.descripcion = item.descripcion
            linea.unidad = item.unidad or ""
            linea.observaciones_bom = item.observaciones or ""
            linea.cantidad_requerida = item.cantidad_solicitada or 0

            # Las líneas nuevas empiezan con disponibilidad 0 hasta revisión de Inventario.
            if linea_creada:
                linea.cantidad_disponible = 0

            linea.save()

        # Cada reenvío debe volver a habilitar la PAW en el tablero de Inventario.
        if ya_estaba_revisada:
            compra.inventario_revisado_en = None
            compra.inventario_revisado_por = None
            campos_compra.extend([
                "inventario_revisado_en",
                "inventario_revisado_por",
            ])

        if campos_compra:
            # Evitar nombres repetidos en update_fields.
            campos_compra = list(dict.fromkeys(campos_compra))
            campos_compra.append("actualizado_en")
            compra.save(update_fields=campos_compra)

        if paw:
            paw.estado_operativo = "EN_REVISION_INVENTARIO"
            paw.save(update_fields=["estado_operativo"])

        registrar_movimiento(
            request=request,
            paw_numero=paw.numero_paw if paw else "",
            modulo="TALLER",
            accion=(
                "BOM actualizado y reenviado a Inventario"
                if ya_estaba_revisada
                else "BOM enviado a Inventario"
            ),
            descripcion=(
                "Taller actualizó el BOM. Se sincronizaron las líneas y se reabrió "
                "la revisión de Inventario."
                if ya_estaba_revisada
                else "Taller envió el BOM para revisión de disponibilidad."
            ),
            objeto=bom,
            datos_nuevos={
                "estado_bom": bom.estado,
                "solicitado_en": str(bom.solicitado_en),
                "purchase_request_id": compra.pk,
                "lineas_nuevas": lineas_nuevas,
                "lineas_actualizadas": lineas_actualizadas,
                "reenvio": ya_estaba_revisada,
            },
        )

        # Siempre vuelve a Inventario. Compras solo verá nuevamente la PAW
        # después de que Inventario confirme la revisión.
        return redirect("inventario:revision_bom_detail", pk=compra.pk)

    return render(request, "bom/enviar_bom_compras.html", {"bom": bom})
