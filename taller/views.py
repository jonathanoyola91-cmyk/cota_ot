from collections import defaultdict
from datetime import date, datetime, timedelta, time
from decimal import Decimal

from django.contrib import messages
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
from .models import CamaraTaller, EnsambleTaller, JornadaTaller


def obtener_bom_seguro(ot):
    try:
        return ot.bom
    except Exception:
        return None


def puede_editar_taller(user):
    return tiene_rol(user, ["TALLER", "ADMIN"])


@login_required
def dashboard(request):
    estados_paw_fuera_operacion = [
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    ]

    # Una OT cuyo PAW ya salió de operación no debe seguir apareciendo
    # como "Pendiente BOM", "Esperando material", "Material parcial", etc.
    # También excluimos OTs cerradas/terminadas.
    ots = (
        WorkOrder.objects
        .select_related("paw")
        .filter(
            Q(paw__isnull=True)
            | Q(paw__requiere_taller=True)
            | Q(paw__requiere_taller__isnull=True, paw__tipo_operacion="ENSAMBLE")
        )
        .exclude(
            Q(paw__estado_operativo__in=estados_paw_fuera_operacion)
            | Q(estado__in=[
                WorkOrder.Status.TERMINADA,
                WorkOrder.Status.CERRADA,
            ])
        )
        .order_by("-numero")
    )

    pendientes_bom = []
    bom_borrador = []
    esperando_material = []
    material_parcial = []
    material_entregado = []

    for ot in ots:
        bom = obtener_bom_seguro(ot)

        if not bom:
            pendientes_bom.append(ot)
            continue

        compra = PurchaseRequest.objects.filter(bom=bom).first()

        entrega = None
        if compra:
            entrega = (
                WorkshopDelivery.objects
                .filter(purchase_request=compra, destino="TALLER")
                .prefetch_related("lineas")
                .first()
            )

        total_lineas = 0
        entregadas = 0
        porcentaje_entrega = 0

        if entrega:
            total_req = Decimal("0")
            total_ent = Decimal("0")

            for linea in entrega.lineas.all():
                req = Decimal(linea.cantidad_requerida or 0)
                ent = Decimal(linea.cantidad_entregada or 0)

                if req <= 0:
                    continue

                total_req += req
                total_ent += min(ent, req)

                total_lineas += 1
                if ent >= req:
                    entregadas += 1

            if total_req > 0:
                porcentaje_entrega = round((total_ent / total_req) * 100)

        item = {
            "ot": ot,
            "bom": bom,
            "compra": compra,
            "entrega": entrega,
            "total_lineas": total_lineas,
            "entregadas": entregadas,
            "porcentaje_entrega": porcentaje_entrega,
        }

        estado_bom = getattr(bom, "estado", "")

        if estado_bom == "BORRADOR":
            bom_borrador.append(item)
        elif entrega and porcentaje_entrega >= 100:
            if not ot.ensamble_ok:
                material_entregado.append(item)
        elif entrega and porcentaje_entrega > 0:
            material_parcial.append(item)
        else:
            esperando_material.append(item)

    historial_ensamble = (
        WorkOrder.objects
        .select_related("paw", "ensamble_confirmado_por")
        .filter(ensamble_ok=True)
        .order_by("-fecha_ensamble_ok", "-actualizado_en")
    )

    return render(request, "taller/dashboard.html", {
        "pendientes_bom": pendientes_bom,
        "bom_borrador": bom_borrador,
        "esperando_material": esperando_material,
        "material_parcial": material_parcial,
        "material_entregado": material_entregado,
        "historial_ensamble": historial_ensamble,

        "total_pendientes_bom": len(pendientes_bom),
        "total_bom_borrador": len(bom_borrador),
        "total_esperando_material": len(esperando_material),
        "total_material_parcial": len(material_parcial),
        "total_material_entregado": len(material_entregado),
        "total_historial_ensamble": historial_ensamble.count(),

        "puede_editar_taller": puede_editar_taller(request.user),
    })


@require_POST
@login_required
def confirmar_ensamble_ok(request, ot_id):
    if not puede_editar_taller(request.user):
        messages.error(request, "No tienes permiso para modificar Taller.")
        return redirect("taller:dashboard")

    ot = get_object_or_404(
        WorkOrder.objects.select_related("paw"),
        numero=ot_id
    )

    if ot.ensamble_ok:
        messages.info(request, "Este ensamble ya fue confirmado.")
        return redirect("taller:dashboard")

    bom = obtener_bom_seguro(ot)

    if not bom:
        messages.error(request, "No se puede cerrar: la OT no tiene BOM.")
        return redirect("taller:dashboard")

    compra = PurchaseRequest.objects.filter(bom=bom).first()

    if not compra:
        messages.error(request, "No hay solicitud de compra.")
        return redirect("taller:dashboard")

    entrega = (
        WorkshopDelivery.objects
        .filter(purchase_request=compra, destino="TALLER")
        .prefetch_related("lineas")
        .first()
    )

    if not entrega:
        messages.error(request, "No hay entrega a taller.")
        return redirect("taller:dashboard")

    total_req = Decimal("0")
    total_ent = Decimal("0")

    for linea in entrega.lineas.all():
        req = Decimal(linea.cantidad_requerida or 0)
        ent = Decimal(linea.cantidad_entregada or 0)

        if req <= 0:
            continue

        total_req += req
        total_ent += min(ent, req)

    if total_req <= 0:
        messages.error(request, "No se puede confirmar: no hay cantidades requeridas válidas.")
        return redirect("taller:dashboard")

    if total_ent < total_req:
        messages.error(request, "Aún hay material pendiente.")
        return redirect("taller:dashboard")

    ot.ensamble_ok = True
    ot.fecha_ensamble_ok = timezone.now()
    ot.ensamble_confirmado_por = request.user
    ot.etapa_taller = WorkOrder.EtapaTaller.TERMINADO
    ot.estado = WorkOrder.Status.TERMINADA
    ot.terminado_en = timezone.now()
    ot.save(update_fields=[
        "ensamble_ok",
        "fecha_ensamble_ok",
        "ensamble_confirmado_por",
        "etapa_taller",
        "estado",
        "terminado_en",
        "actualizado_en",
    ])

    if ot.paw:
        ot.paw.estado_operativo = "PRODUCTO_OK"
        ot.paw.save(update_fields=["estado_operativo"])

        if ot.paw.listo_para_facturar:
            messages.success(
                request,
                "Ensamble confirmado. El PAW quedó listo para facturación.",
            )
        elif ot.paw.aplica_campo:
            messages.success(
                request,
                "Ensamble confirmado. Taller finalizó y el PAW queda pendiente de Campo.",
            )
        else:
            messages.success(request, "Ensamble confirmado correctamente.")
    else:
        messages.success(request, "Ensamble confirmado correctamente.")

    return redirect("taller:dashboard")

@login_required
def camaras_taller(request):

    activas = (
        CamaraTaller.objects
        .filter(paw__isnull=True)
        .order_by("fecha_ingreso", "id")
    )

    historial = (
        CamaraTaller.objects
        .filter(paw__isnull=False)
        .select_related("paw")
        .order_by("-actualizado_en")
    )

    return render(request, "taller/camaras_taller.html", {
        "activas": activas,
        "historial": historial,
        "total_activas": activas.count(),
    })


@login_required
def camara_nueva(request):

    if request.method == "POST":

        cliente = request.POST.get("cliente", "").strip()
        marca = request.POST.get("marca", "").strip()
        serial = request.POST.get("serial", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        fecha_ingreso = request.POST.get("fecha_ingreso")
        fecha_tear_down = request.POST.get("fecha_tear_down") or None
        observaciones = request.POST.get("observaciones", "").strip()

        if not cliente or not serial or not fecha_ingreso:
            messages.error(
                request,
                "Cliente, serial y fecha de ingreso son obligatorios."
            )
            return redirect("taller:camara_nueva")

        CamaraTaller.objects.create(
            cliente=cliente,
            marca=marca,
            serial=serial,
            modelo=modelo,
            fecha_ingreso=fecha_ingreso,
            fecha_tear_down=fecha_tear_down,
            estado=CamaraTaller.Estado.RECIBIDA,
            observaciones=observaciones,
        )

        messages.success(
            request,
            f"Cámara serial {serial} registrada en Taller."
        )

        return redirect("taller:camaras_taller")

    return render(request, "taller/camara_nueva.html")

@login_required
def camara_editar(request, camara_id):

    camara = get_object_or_404(
        CamaraTaller,
        id=camara_id
    )

    if request.method == "POST":

        cliente = request.POST.get("cliente", "").strip()
        marca = request.POST.get("marca", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        serial = request.POST.get("serial", "").strip()
        fecha_ingreso = request.POST.get("fecha_ingreso")
        fecha_tear_down = request.POST.get("fecha_tear_down") or None
        estado = request.POST.get("estado")
        observaciones = request.POST.get("observaciones", "").strip()

        if not cliente or not serial or not fecha_ingreso:
            messages.error(
                request,
                "Cliente, serial y fecha de ingreso son obligatorios."
            )
            return redirect(
                "taller:camara_editar",
                camara_id=camara.id
            )

        estados_validos = [
            valor for valor, texto in CamaraTaller.Estado.choices
        ]

        if estado not in estados_validos:
            messages.error(
                request,
                "El estado seleccionado no es válido."
            )
            return redirect(
                "taller:camara_editar",
                camara_id=camara.id
            )

        camara.cliente = cliente
        camara.marca = marca
        camara.modelo = modelo
        camara.serial = serial
        camara.fecha_ingreso = fecha_ingreso
        camara.fecha_tear_down = fecha_tear_down
        camara.estado = estado
        camara.observaciones = observaciones

        camara.save()

        messages.success(
            request,
            f"Cámara serial {camara.serial} actualizada correctamente."
        )

        return redirect("taller:camaras_taller")

    return render(
        request,
        "taller/camara_editar.html",
        {
            "camara": camara,
            "estados": CamaraTaller.Estado.choices,
        }
    )

# ============================================================
# CONTROL DE HORAS DE ENSAMBLE - TALLER
# ============================================================

def _puede_taller(user):
    return tiene_rol(user, ["TALLER", "INGENIERIA", "GERENTE", "ADMIN"])


def _puede_ver_reporte_horas(user):
    return tiene_rol(user, ["FINANZAS", "GERENTE", "ADMIN"])


def _parse_fecha(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@login_required
def dashboard_horas_taller(request):
    if not _puede_taller(request.user) and not _puede_ver_reporte_horas(request.user):
        messages.error(request, "No tienes acceso al control de horas de Taller.")
        return redirect("/")

    # Todo PAW creado como ENSAMBLE aparece en Taller sin depender de OT
    # ni de que CamaraTaller tenga el PAW relacionado.
    estados_fuera_operacion = ["EN_FACTURACION", "FACTURADO", "RADICADO"]

    paws_disponibles = (
        Paw.objects
        .select_related("cotizacion")
        .filter(
            Q(requiere_taller=True)
            | Q(
                requiere_taller__isnull=True,
                tipo_operacion=Paw.TipoOperacion.ENSAMBLE,
            )
        )
        .exclude(estado_operativo__in=estados_fuera_operacion)
        .filter(ensamble_horas_taller__isnull=True)
        .order_by("-creado_en")
    )

    ensambles_base = (
        EnsambleTaller.objects
        .select_related("paw", "paw__cotizacion", "responsable")
        .prefetch_related("tecnicos", "jornadas")
        .filter(paw__isnull=False)
    )

    # Controles que todavía pueden recibir jornadas o ajustes.
    ensambles_abiertos = (
        ensambles_base
        .exclude(estado=EnsambleTaller.Estado.FINALIZADO)
        .order_by("-actualizado_en")
    )

    # Histórico de controles de horas ya cerrados.
    ensambles_finalizados = (
        ensambles_base
        .filter(estado=EnsambleTaller.Estado.FINALIZADO)
        .order_by("-fecha_fin", "-actualizado_en")
    )

    return render(request, "taller_horas/dashboard.html", {
        "paws_disponibles": paws_disponibles,
        "ensambles": ensambles_base,
        "ensambles_abiertos": ensambles_abiertos,
        "ensambles_finalizados": ensambles_finalizados,
        "total_controles": ensambles_base.count(),
        "total_abiertos": ensambles_abiertos.count(),
        "total_finalizados": ensambles_finalizados.count(),
        "total_pendientes_iniciar": paws_disponibles.count(),
        "puede_operar": _puede_taller(request.user),
        "puede_reporte": _puede_ver_reporte_horas(request.user),
    })


@login_required
def iniciar_ensamble(request, paw_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para iniciar controles de horas de Taller.")
        return redirect("/")

    paw = get_object_or_404(
        Paw.objects.select_related("cotizacion"),
        id=paw_id,
    )

    if not paw.aplica_taller:
        messages.error(request, "Este PAW no tiene habilitado el alcance de Taller / reparación.")
        return redirect("taller:horas_dashboard")

    existente = EnsambleTaller.objects.filter(paw=paw).first()
    if existente:
        return redirect("taller:horas_detalle", ensamble_id=existente.id)

    if request.method == "POST":
        form = IniciarEnsambleForm(request.POST)
        if form.is_valid():
            ensamble = form.save(commit=False)
            ensamble.paw = paw
            ensamble.responsable = request.user
            ensamble.save()
            messages.success(
                request,
                f"Control de horas iniciado para el PAW {paw.numero_paw}."
            )
            return redirect("taller:horas_asignar_tecnicos", ensamble_id=ensamble.id)
    else:
        form = IniciarEnsambleForm(initial={"fecha_inicio": timezone.localdate()})

    return render(request, "taller_horas/iniciar_ensamble.html", {
        "paw": paw,
        "form": form,
    })


@login_required
def detalle_ensamble(request, ensamble_id):
    if not _puede_taller(request.user) and not _puede_ver_reporte_horas(request.user):
        messages.error(request, "No tienes acceso a este control de horas.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw", "paw__cotizacion", "responsable")
        .prefetch_related("tecnicos", "jornadas", "jornadas__tecnico"),
        id=ensamble_id,
    )

    camara_relacionada = None
    if ensamble.paw_id:
        camara_relacionada = (
            CamaraTaller.objects
            .filter(paw=ensamble.paw)
            .order_by("-actualizado_en")
            .first()
        )

    return render(request, "taller_horas/detalle.html", {
        "ensamble": ensamble,
        "jornadas": ensamble.jornadas.all(),
        "camara_relacionada": camara_relacionada,
        "puede_operar": _puede_taller(request.user),
        "puede_reporte": _puede_ver_reporte_horas(request.user),
    })


@login_required
def asignar_tecnicos(request, ensamble_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para asignar técnicos.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw")
        .prefetch_related("tecnicos"),
        id=ensamble_id,
    )

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.error(request, "No puedes modificar técnicos de un control finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if request.method == "POST":
        form = AsignarTecnicosTallerForm(request.POST, ensamble=ensamble)
        if form.is_valid():
            form.save()
            messages.success(request, "Técnicos de Taller actualizados.")
            return redirect("taller:horas_detalle", ensamble_id=ensamble.id)
    else:
        form = AsignarTecnicosTallerForm(ensamble=ensamble)

    return render(request, "taller_horas/asignar_tecnicos.html", {
        "ensamble": ensamble,
        "form": form,
    })


@login_required
def crear_jornada(request, ensamble_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para registrar jornadas de Taller.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw")
        .prefetch_related("tecnicos"),
        id=ensamble_id,
    )

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.error(request, "No puedes registrar horas en un control finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if not ensamble.tecnicos.exists():
        messages.error(request, "Primero debes asignar los técnicos involucrados.")
        return redirect("taller:horas_asignar_tecnicos", ensamble_id=ensamble.id)

    if request.method == "POST":
        form = JornadaTallerForm(request.POST, ensamble=ensamble)

        # La instancia debe conocer el ensamble ANTES de form.is_valid().
        # Así las validaciones del modelo (incluido solapamiento de horarios)
        # aparecen como errores del formulario y no generan ValidationError 500.
        form.instance.ensamble = ensamble

        if form.is_valid():
            jornada = form.save(commit=False)
            jornada.ensamble = ensamble
            jornada.registrado_por = request.user
            jornada.save()
            messages.success(request, "Actividad registrada y horas calculadas automáticamente.")
            return redirect("taller:horas_detalle", ensamble_id=ensamble.id)
    else:
        ahora = timezone.localtime()
        form = JornadaTallerForm(
            ensamble=ensamble,
            initial={
                "fecha": timezone.localdate(),
                "hora_entrada": ahora.strftime("%H:%M"),
            },
        )

    return render(request, "taller_horas/jornada_form.html", {
        "ensamble": ensamble,
        "form": form,
        "modo": "crear",
    })


@login_required
def editar_jornada(request, jornada_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para editar jornadas de Taller.")
        return redirect("/")

    jornada = get_object_or_404(
        JornadaTaller.objects
        .select_related("ensamble", "ensamble__paw", "tecnico"),
        id=jornada_id,
    )
    ensamble = jornada.ensamble

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.error(request, "No puedes editar jornadas de un control finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if request.method == "POST":
        form = JornadaTallerForm(request.POST, instance=jornada, ensamble=ensamble)
        if form.is_valid():
            form.save()
            messages.success(request, "Jornada actualizada.")
            return redirect("taller:horas_detalle", ensamble_id=ensamble.id)
    else:
        form = JornadaTallerForm(instance=jornada, ensamble=ensamble)

    return render(request, "taller_horas/jornada_form.html", {
        "ensamble": ensamble,
        "jornada": jornada,
        "form": form,
        "modo": "editar",
    })


@require_POST
@login_required
def finalizar_ensamble(request, ensamble_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para finalizar controles de horas de Taller.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw")
        .prefetch_related("jornadas"),
        id=ensamble_id,
    )

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.info(request, "Este control de horas ya estaba finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if not ensamble.jornadas.exists():
        messages.error(request, "No puedes finalizar sin registrar al menos una jornada.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    # CIERRE EXCLUSIVAMENTE INTERNO.
    # No cambia paw.estado_operativo, tipo_operacion ni el estado de CamaraTaller.
    ensamble.estado = EnsambleTaller.Estado.FINALIZADO
    ensamble.fecha_fin = timezone.localdate()
    ensamble.save(update_fields=["estado", "fecha_fin", "actualizado_en"])

    messages.success(
        request,
        "Control de horas finalizado internamente. El flujo principal del PAW no fue modificado."
    )
    return redirect("taller:horas_detalle", ensamble_id=ensamble.id)



def _merge_intervalos(intervalos):
    """
    Une intervalos que se tocan o se superponen.
    Devuelve una lista de pares (inicio, fin) sin doble conteo.
    """
    if not intervalos:
        return []

    ordenados = sorted(intervalos, key=lambda x: x[0])
    resultado = [list(ordenados[0])]

    for inicio, fin in ordenados[1:]:
        ultimo = resultado[-1]
        if inicio <= ultimo[1]:
            if fin > ultimo[1]:
                ultimo[1] = fin
        else:
            resultado.append([inicio, fin])

    return [(i, f) for i, f in resultado]


def _clasificar_intervalos_dia(intervalos):
    """
    Consolida todos los PAW trabajados por un técnico en un mismo día y
    clasifica el tiempo efectivo sin duplicar intervalos.
    """
    if not intervalos:
        cero = Decimal("0.00")
        return cero, cero, cero, cero

    intervalos_unidos = _merge_intervalos(intervalos)

    ordinarias = Decimal("0.00")
    extra_diurna = Decimal("0.00")
    extra_nocturna = Decimal("0.00")

    for inicio, fin in intervalos_unidos:
        cursor = inicio.date()
        fin_dia = fin.date()

        while cursor <= fin_dia:
            dia_sig = cursor + timedelta(days=1)

            tramos_ordinarios = [
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=7)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=12)),
                ),
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=13)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=16)),
                ),
            ]

            tramos_extra_diurna = [
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=6)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=7)),
                ),
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=16)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=19)),
                ),
            ]

            tramos_extra_nocturna = [
                (
                    datetime.combine(cursor, datetime.min.time()),
                    datetime.combine(cursor, datetime.min.time().replace(hour=6)),
                ),
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=19)),
                    datetime.combine(dia_sig, datetime.min.time()),
                ),
            ]

            for desde, hasta in tramos_ordinarios:
                ordinarias += JornadaTaller._horas_interseccion(inicio, fin, desde, hasta)

            for desde, hasta in tramos_extra_diurna:
                extra_diurna += JornadaTaller._horas_interseccion(inicio, fin, desde, hasta)

            for desde, hasta in tramos_extra_nocturna:
                extra_nocturna += JornadaTaller._horas_interseccion(inicio, fin, desde, hasta)

            cursor = dia_sig

    total = ordinarias + extra_diurna + extra_nocturna
    return ordinarias, extra_diurna, extra_nocturna, total


@login_required
def reporte_horas(request):
    if not _puede_ver_reporte_horas(request.user):
        messages.error(request, "No tienes acceso al reporte contable de horas de Taller.")
        return redirect("/")

    hoy = timezone.localdate()
    fecha_inicio = _parse_fecha(request.GET.get("fecha_inicio")) or hoy.replace(day=1)
    fecha_fin = _parse_fecha(request.GET.get("fecha_fin")) or hoy

    jornadas = (
        JornadaTaller.objects
        .filter(fecha__range=[fecha_inicio, fecha_fin])
        .select_related("tecnico", "ensamble", "ensamble__paw")
        .order_by("tecnico__tecnico", "fecha", "hora_entrada")
    )

    # Agrupamos por técnico y fecha para consolidar todos los PAW del día.
    por_tecnico_fecha = defaultdict(lambda: {
        "intervalos": [],
        "detalle": [],
    })

    for j in jornadas:
        clave = (j.tecnico.tecnico, j.fecha)
        inicio, fin = j._intervalo_real()
        por_tecnico_fecha[clave]["intervalos"].append((inicio, fin))
        por_tecnico_fecha[clave]["detalle"].append(j)

    resumen = defaultdict(lambda: {
        "ordinarias": Decimal("0.00"),
        "extra_diurna": Decimal("0.00"),
        "extra_nocturna": Decimal("0.00"),
        "total": Decimal("0.00"),
        "detalle": [],
        "dias": [],
    })

    total_ord = Decimal("0.00")
    total_ed = Decimal("0.00")
    total_en = Decimal("0.00")
    total_general = Decimal("0.00")

    for (nombre, fecha), info in sorted(por_tecnico_fecha.items(), key=lambda x: (x[0][0], x[0][1])):
        ord_dia, ed_dia, en_dia, total_dia = _clasificar_intervalos_dia(info["intervalos"])

        data = resumen[nombre]
        data["ordinarias"] += ord_dia
        data["extra_diurna"] += ed_dia
        data["extra_nocturna"] += en_dia
        data["total"] += total_dia
        data["detalle"].extend(info["detalle"])
        data["dias"].append({
            "fecha": fecha,
            "ordinarias": ord_dia,
            "extra_diurna": ed_dia,
            "extra_nocturna": en_dia,
            "total": total_dia,
            "detalle": info["detalle"],
        })

        total_ord += ord_dia
        total_ed += ed_dia
        total_en += en_dia
        total_general += total_dia

    return render(request, "taller_horas/reporte_horas.html", {
        "resumen": dict(resumen),
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_ordinarias": total_ord,
        "total_extra_diurna": total_ed,
        "total_extra_nocturna": total_en,
        "total_general": total_general,
    })


@login_required
def reporte_horas_empleado(request):
    if not _puede_ver_reporte_horas(request.user):
        messages.error(
            request,
            "No tienes acceso al reporte individual de horas extra de Taller."
        )
        return redirect("/")

    tecnico = request.GET.get("tecnico", "").strip()

    if not tecnico:
        messages.error(request, "Debes indicar el técnico.")
        return redirect("taller:horas_reporte")

    hoy = timezone.localdate()
    corte_inicio, corte_fin = _periodo_corte_27(hoy)

    fecha_inicio = (
        _parse_fecha(request.GET.get("fecha_inicio"))
        or corte_inicio
    )

    fecha_fin = (
        _parse_fecha(request.GET.get("fecha_fin"))
        or corte_fin
    )

    jornadas = (
        JornadaTaller.objects
        .filter(
            tecnico__tecnico=tecnico,
            fecha__range=[fecha_inicio, fecha_fin],
            ensamble__estado=EnsambleTaller.Estado.FINALIZADO,
        )
        .select_related(
            "tecnico",
            "ensamble",
            "ensamble__paw",
        )
        .order_by("fecha", "hora_entrada")
    )

    # Consolidar por fecha todos los PAW del empleado para evitar doble conteo.
    por_fecha = defaultdict(list)
    for jornada in jornadas:
        por_fecha[jornada.fecha].append(jornada._intervalo_real())

    total_ordinarias = Decimal("0.00")
    total_extra_diurna = Decimal("0.00")
    total_extra_nocturna = Decimal("0.00")
    total_general = Decimal("0.00")

    for intervalos in por_fecha.values():
        ord_dia, ed_dia, en_dia, total_dia = _clasificar_intervalos_dia(intervalos)
        total_ordinarias += ord_dia
        total_extra_diurna += ed_dia
        total_extra_nocturna += en_dia
        total_general += total_dia

    return render(
        request,
        "taller_horas/reporte_horas_empleado.html",
        {
            "tecnico": tecnico,
            "jornadas": jornadas,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "total_ordinarias": total_ordinarias,
            "total_extra_diurna": total_extra_diurna,
            "total_extra_nocturna": total_extra_nocturna,
            "total_general": total_general,
        }
    )

def _periodo_corte_27(fecha_base):
    if fecha_base.day <= 27:

        if fecha_base.month == 1:
            fecha_inicio = date(
                fecha_base.year - 1,
                12,
                28
            )
        else:
            fecha_inicio = date(
                fecha_base.year,
                fecha_base.month - 1,
                28
            )

        fecha_fin = date(
            fecha_base.year,
            fecha_base.month,
            27
        )

    else:

        fecha_inicio = date(
            fecha_base.year,
            fecha_base.month,
            28
        )

        if fecha_base.month == 12:
            fecha_fin = date(
                fecha_base.year + 1,
                1,
                27
            )
        else:
            fecha_fin = date(
                fecha_base.year,
                fecha_base.month + 1,
                27
            )

    return fecha_inicio, fecha_fin