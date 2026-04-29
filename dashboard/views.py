from datetime import date

from django.shortcuts import render
from django.db.models import Sum

from quotes.models import Quotation
from paw_app.models import Paw


def dashboard_home(request):
    cotizaciones = Quotation.objects.all()
    paws = Paw.objects.all().select_related("cotizacion", "creado_por")

    total_cotizaciones = cotizaciones.count()
    cotizaciones_adjudicadas = cotizaciones.filter(estado="ADJUDICADA").count()
    cotizaciones_evaluacion = cotizaciones.filter(estado="EVALUACION").count()

    valor_adjudicado = cotizaciones.filter(
        estado="ADJUDICADA"
    ).aggregate(total=Sum("valor"))["total"] or 0

    total_paws = paws.count()
    paw_compras = paws.filter(estado_operativo="EN_COMPRAS").count()
    paw_finanzas = paws.filter(estado_operativo="EN_FINANZAS").count()
    paw_aprobacion = paws.filter(estado_operativo="EN_APROBACION").count()
    paw_material_recibido = paws.filter(estado_operativo="MATERIAL_RECIBIDO").count()
    paw_taller = paws.filter(estado_operativo="ENTREGADO_TALLER").count()
    producto_listo = paws.filter(estado_operativo="PRODUCTO_OK").count()
    pendientes_facturar = paws.filter(estado_operativo="PRODUCTO_OK").count()

    paws_criticos = paws.filter(
        estado_operativo__in=[
            "EN_COMPRAS",
            "EN_FINANZAS",
            "EN_APROBACION",
            "MATERIAL_RECIBIDO",
            "ENTREGADO_TALLER",
        ]
    ).order_by("-actualizado_en")[:10]

    hoy = date.today()
    paws_atrasados = 0
    paws_proximos = 0
    paws_entregas = []

    for paw in paws.exclude(fecha_entrega=None).order_by("fecha_entrega"):
        dias = (paw.fecha_entrega - hoy).days

        if dias < 0:
            semaforo = "rojo"
            texto = "Atrasado"
            paws_atrasados += 1
        elif dias <= 3:
            semaforo = "amarillo"
            texto = "Próximo"
            paws_proximos += 1
        else:
            semaforo = "verde"
            texto = "En tiempo"

        paws_entregas.append({
            "paw": paw,
            "dias": dias,
            "semaforo": semaforo,
            "texto": texto,
        })

    ultimas_cotizaciones = cotizaciones.order_by("-creado_en")[:5]
    ultimos_paws = paws.order_by("-creado_en")[:5]

    es_compras = request.user.is_superuser or request.user.groups.filter(name="COMPRAS").exists()
    es_finanzas = request.user.is_superuser or request.user.groups.filter(name="FINANZAS").exists()
    es_gerente = request.user.is_superuser or request.user.groups.filter(name="GERENTE").exists()
    es_inventario = request.user.is_superuser or request.user.groups.filter(name="INVENTARIO").exists()
    es_comercial = request.user.is_superuser or request.user.groups.filter(name="COMERCIAL").exists()

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

        "paws_criticos": paws_criticos,
        "paws_entregas": paws_entregas,
        "paws_atrasados": paws_atrasados,
        "paws_proximos": paws_proximos,

        "ultimas_cotizaciones": ultimas_cotizaciones,
        "ultimos_paws": ultimos_paws,

        "es_compras": es_compras,
        "es_finanzas": es_finanzas,
        "es_gerente": es_gerente,
        "es_inventario": es_inventario,
        "es_comercial": es_comercial,
    })