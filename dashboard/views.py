from datetime import date

from django.shortcuts import render
from django.db.models import Sum, Q
from django.contrib.auth.decorators import login_required

from quotes.models import Quotation
from paw_app.models import Paw


@login_required
def dashboard_home(request):
    """Dashboard ejecutivo de IMPETUS CONTROL.

    Mantiene la lógica original y agrega indicadores derivados únicamente
    de datos que ya existen en Quotation y Paw.
    """

    cotizaciones = Quotation.objects.all()

    # Solo PAW operativamente activos / pendientes.
    paws = Paw.objects.select_related("cotizacion", "creado_por").exclude(
        Q(estado_operativo__in=[
            "EN_FACTURACION",
            "FACTURADO",
            "RADICADO",
        ]) | Q(factura__isnull=False)
    )

    # ------------------------------------------------------------------
    # Comercial
    # ------------------------------------------------------------------
    total_cotizaciones = cotizaciones.count()
    cotizaciones_adjudicadas = cotizaciones.filter(estado="ADJUDICADA").count()
    cotizaciones_evaluacion = cotizaciones.filter(estado="EVALUACION").count()

    valor_adjudicado = cotizaciones.filter(
        estado="ADJUDICADA"
    ).aggregate(total=Sum("valor"))["total"] or 0

    # ------------------------------------------------------------------
    # Flujo PAW
    # ------------------------------------------------------------------
    total_paws = paws.count()
    paw_compras = paws.filter(estado_operativo="EN_COMPRAS").count()
    paw_finanzas = paws.filter(estado_operativo="EN_FINANZAS").count()
    paw_aprobacion = paws.filter(estado_operativo="EN_APROBACION").count()
    paw_material_recibido = paws.filter(estado_operativo="MATERIAL_RECIBIDO").count()
    paw_taller = paws.filter(estado_operativo="ENTREGADO_TALLER").count()
    producto_listo = paws.filter(estado_operativo="PRODUCTO_OK").count()

    pendientes_facturar = producto_listo

    paws_pendientes_facturar = paws.filter(
        estado_operativo="PRODUCTO_OK"
    ).order_by("-actualizado_en")[:5]

    bloqueos_finanzas_qs = paws.filter(
        estado_operativo__in=["EN_FINANZAS", "EN_APROBACION"]
    )
    total_bloqueos_finanzas = bloqueos_finanzas_qs.count()
    bloqueos_finanzas = bloqueos_finanzas_qs.order_by("-actualizado_en")[:5]

    bloqueos_facturacion = paws.filter(
        estado_operativo="PRODUCTO_OK"
    ).order_by("-actualizado_en")[:5]

    paws_criticos = paws.filter(
        estado_operativo__in=[
            "EN_COMPRAS",
            "EN_FINANZAS",
            "EN_APROBACION",
            "MATERIAL_RECIBIDO",
            "ENTREGADO_TALLER",
        ]
    ).order_by("-actualizado_en")[:10]

    # ------------------------------------------------------------------
    # Entregas / semáforo
    # ------------------------------------------------------------------
    hoy = date.today()

    paws_atrasados = 0
    paws_proximos = 0
    paws_en_tiempo = 0
    paws_entregas = []

    for paw in paws.exclude(fecha_entrega=None).order_by("fecha_entrega"):
        dias = (paw.fecha_entrega - hoy).days

        if dias < 0:
            semaforo = "rojo"
            texto = "Atrasado"
            prioridad = "Alta"
            paws_atrasados += 1
        elif dias <= 3:
            semaforo = "amarillo"
            texto = "Próximo"
            prioridad = "Media"
            paws_proximos += 1
        else:
            semaforo = "verde"
            texto = "En tiempo"
            prioridad = "Baja"
            paws_en_tiempo += 1

        paws_entregas.append({
            "paw": paw,
            "dias": dias,
            "semaforo": semaforo,
            "texto": texto,
            "prioridad": prioridad,
        })

    total_entregas_programadas = len(paws_entregas)

    # Indicador de salud del calendario de PAW activos con fecha de entrega.
    # No se presenta como cumplimiento histórico; solo refleja el estado actual.
    if total_entregas_programadas:
        salud_entregas = round((paws_en_tiempo / total_entregas_programadas) * 100)
    else:
        salud_entregas = 100

    # Cantidad de alertas ejecutivas visibles en el panel derecho.
    total_alertas = (
        paws_atrasados
        + total_bloqueos_finanzas
        + pendientes_facturar
    )

    # ------------------------------------------------------------------
    # Actividad reciente
    # ------------------------------------------------------------------
    ultimas_cotizaciones = cotizaciones.order_by("-creado_en")[:5]
    ultimos_paws = paws.order_by("-creado_en")[:5]

    # ------------------------------------------------------------------
    # Permisos (se conserva la lógica existente)
    # ------------------------------------------------------------------
    es_compras = (
        request.user.is_superuser
        or request.user.groups.filter(name__in=["COMPRAS", "COMPRAS_OIL"]).exists()
    )

    es_finanzas = (
        request.user.is_superuser
        or request.user.groups.filter(name="FINANZAS").exists()
    )

    es_gerente = (
        request.user.is_superuser
        or request.user.groups.filter(name__in=["GERENTE", "gerencia"]).exists()
    )

    es_inventario = (
        request.user.is_superuser
        or request.user.groups.filter(name="INVENTARIO").exists()
    )

    es_comercial = (
        request.user.is_superuser
        or request.user.groups.filter(name__in=["COMERCIAL", "Comercial"]).exists()
    )

    es_taller = (
        request.user.is_superuser
        or request.user.groups.filter(name__in=["TALLER", "Taller"]).exists()
    )

    es_ingenieria = (
        request.user.is_superuser
        or request.user.groups.filter(name__in=["INGENIERIA", "Ingeniería"]).exists()
    )

    es_campo = (
        request.user.is_superuser
        or request.user.groups.filter(name="CAMPO").exists()
    )

    return render(request, "dashboard/index.html", {
        "total_cotizaciones": total_cotizaciones,
        "cotizaciones_adjudicadas": cotizaciones_adjudicadas,
        "cotizaciones_evaluacion": cotizaciones_evaluacion,
        "valor_adjudicado": valor_adjudicado,

        "total_paws": total_paws,
        "paw_compras": paw_compras,
        "paw_finanzas": paw_finanzas,
        "paw_aprobacion": paw_aprobacion,
        "paw_material_recibido": paw_material_recibido,
        "paw_taller": paw_taller,
        "producto_listo": producto_listo,

        "pendientes_facturar": pendientes_facturar,
        "bloqueos_finanzas": bloqueos_finanzas,
        "total_bloqueos_finanzas": total_bloqueos_finanzas,
        "bloqueos_facturacion": bloqueos_facturacion,

        "paws_criticos": paws_criticos,
        "paws_entregas": paws_entregas,
        "paws_atrasados": paws_atrasados,
        "paws_proximos": paws_proximos,
        "paws_en_tiempo": paws_en_tiempo,
        "total_entregas_programadas": total_entregas_programadas,
        "salud_entregas": salud_entregas,
        "total_alertas": total_alertas,
        "paws_pendientes_facturar": paws_pendientes_facturar,

        "ultimas_cotizaciones": ultimas_cotizaciones,
        "ultimos_paws": ultimos_paws,

        "es_compras": es_compras,
        "es_finanzas": es_finanzas,
        "es_gerente": es_gerente,
        "es_inventario": es_inventario,
        "es_comercial": es_comercial,
        "es_taller": es_taller,
        "es_ingenieria": es_ingenieria,
        "es_campo": es_campo,
    })
