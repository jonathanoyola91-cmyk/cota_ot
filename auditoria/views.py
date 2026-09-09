from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect

from .models import MovimientoSistema


def _puede_ver_auditoria(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    grupos_permitidos = {
        "Administracion",
        "gerencia",
        "Ingeniería",
    }

    return user.groups.filter(name__in=grupos_permitidos).exists()


@login_required
def tablero_movimientos(request):
    if not _puede_ver_auditoria(request.user):
        messages.error(request, "No tienes permiso para consultar la auditoría.")
        return redirect("/")

    qs = MovimientoSistema.objects.select_related("usuario").all()

    paw = (request.GET.get("paw") or "").strip()
    modulo = (request.GET.get("modulo") or "").strip()
    usuario = (request.GET.get("usuario") or "").strip()
    buscar = (request.GET.get("q") or "").strip()
    fecha_desde = (request.GET.get("desde") or "").strip()
    fecha_hasta = (request.GET.get("hasta") or "").strip()

    if paw:
        qs = qs.filter(paw_numero__icontains=paw)

    if modulo:
        qs = qs.filter(modulo=modulo)

    if usuario:
        qs = qs.filter(
            Q(usuario__username__icontains=usuario)
            | Q(usuario__first_name__icontains=usuario)
            | Q(usuario__last_name__icontains=usuario)
        )

    if buscar:
        qs = qs.filter(
            Q(accion__icontains=buscar)
            | Q(descripcion__icontains=buscar)
            | Q(objeto_tipo__icontains=buscar)
        )

    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)

    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    modulos = (
        MovimientoSistema.objects
        .exclude(modulo="")
        .values_list("modulo", flat=True)
        .distinct()
        .order_by("modulo")
    )

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "auditoria/tablero_movimientos.html",
        {
            "page_obj": page_obj,
            "modulos": modulos,
            "filtros": {
                "paw": paw,
                "modulo": modulo,
                "usuario": usuario,
                "q": buscar,
                "desde": fecha_desde,
                "hasta": fecha_hasta,
            },
        },
    )
