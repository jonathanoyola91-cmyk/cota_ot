from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.roles import tiene_rol
from .forms import ClienteForm, QuotationForm
from .models import Cliente, Quotation


# Consecutivos iniciales por empresa.
# Si ya existe una cotización mayor en base de datos, el sistema continúa desde esa.
CONSECUTIVOS_BASE = {
    Quotation.Empresa.IMPETUS: 276,
    Quotation.Empresa.OIL_GAS: 1615,
}


def _usuario_puede_ver_cotizaciones(user):
    return tiene_rol(user, ["COMERCIAL", "GERENTE", "ADMIN"])


def _extraer_consecutivo(numero):
    """
    Convierte COT-00276 en 276.
    Si el formato no sirve, retorna None para ignorarlo.
    """
    if not numero:
        return None

    try:
        return int(str(numero).split("-")[-1])
    except (TypeError, ValueError):
        return None


def generar_numero_cotizacion(empresa=None):
    """
    Genera el siguiente consecutivo por empresa.

    IMPETUS inicia/continúa desde COT-00276.
    OIL_GAS inicia/continúa desde COT-01615.

    Ejemplos:
    - Si no hay cotizaciones de IMPETUS mayores a 276, la próxima será COT-00277.
    - Si no hay cotizaciones de OIL_GAS mayores a 1615, la próxima será COT-01616.
    """
    empresa = empresa or Quotation.Empresa.IMPETUS

    if empresa not in dict(Quotation.Empresa.choices):
        empresa = Quotation.Empresa.IMPETUS

    base = CONSECUTIVOS_BASE.get(empresa, 0)
    mayor = base

    numeros = Quotation.objects.filter(
        empresa=empresa,
        numero_cotizacion__startswith="COT-",
    ).values_list("numero_cotizacion", flat=True)

    for numero in numeros:
        consecutivo = _extraer_consecutivo(numero)
        if consecutivo is not None and consecutivo > mayor:
            mayor = consecutivo

    return f"COT-{mayor + 1:05d}"


@login_required
def lista_cotizaciones(request):
    if not _usuario_puede_ver_cotizaciones(request.user):
        messages.error(request, "No tienes acceso a Cotizaciones.")
        return redirect("/")

    cotizaciones = Quotation.objects.all().order_by("-id")

    total = cotizaciones.count()
    evaluacion = cotizaciones.filter(estado=Quotation.Estado.EVALUACION).count()
    adjudicadas = cotizaciones.filter(estado=Quotation.Estado.ADJUDICADA).count()
    cerradas = cotizaciones.filter(estado=Quotation.Estado.CERRADA).count()

    valor_adjudicado = cotizaciones.filter(
        estado=Quotation.Estado.ADJUDICADA
    ).aggregate(total=Sum("valor"))["total"] or 0

    con_paw = cotizaciones.filter(paws__isnull=False).distinct().count()
    sin_paw = adjudicadas - con_paw

    return render(request, "quotes/lista.html", {
        "cotizaciones": cotizaciones,
        "total": total,
        "evaluacion": evaluacion,
        "adjudicadas": adjudicadas,
        "cerradas": cerradas,
        "valor_adjudicado": valor_adjudicado,
        "con_paw": con_paw,
        "sin_paw": sin_paw,
    })


@login_required
def crear_cotizacion(request):
    if not _usuario_puede_ver_cotizaciones(request.user):
        messages.error(request, "No tienes acceso a Cotizaciones.")
        return redirect("/")

    if request.method == "POST":
        form = QuotationForm(request.POST)
        if form.is_valid():
            cotizacion = form.save(commit=False)
            cotizacion.numero_cotizacion = generar_numero_cotizacion(cotizacion.empresa)
            cotizacion.save()
            messages.success(
                request,
                f"Cotización {cotizacion.numero_cotizacion} creada correctamente."
            )
            return redirect("detalle_cotizacion", pk=cotizacion.pk)
    else:
        form = QuotationForm()

    empresa_inicial = form.initial.get("empresa") or Quotation.Empresa.IMPETUS

    return render(request, "quotes/quotation_form.html", {
        "form": form,
        "modo": "crear",
        "numero_preview": generar_numero_cotizacion(empresa_inicial),
    })


@login_required
def editar_cotizacion(request, pk):
    if not _usuario_puede_ver_cotizaciones(request.user):
        messages.error(request, "No tienes acceso a Cotizaciones.")
        return redirect("/")

    cotizacion = get_object_or_404(Quotation, pk=pk)

    if request.method == "POST":
        form = QuotationForm(request.POST, instance=cotizacion)
        if form.is_valid():
            form.save()
            messages.success(request, "Cotización actualizada correctamente.")
            return redirect("detalle_cotizacion", pk=cotizacion.pk)
    else:
        form = QuotationForm(instance=cotizacion)

    return render(request, "quotes/quotation_form.html", {
        "form": form,
        "modo": "editar",
        "cotizacion": cotizacion,
        "numero_preview": cotizacion.numero_cotizacion,
    })


@login_required
def detalle_cotizacion(request, pk):
    if not _usuario_puede_ver_cotizaciones(request.user):
        messages.error(request, "No tienes acceso a Cotizaciones.")
        return redirect("/")

    cotizacion = get_object_or_404(Quotation, pk=pk)

    return render(request, "quotes/detail.html", {
        "cotizacion": cotizacion,
    })


@login_required
def numero_cotizacion_preview(request):
    """
    Endpoint opcional para actualizar el número automático cuando cambia el selector Empresa.
    Usar desde JS con: ?empresa=IMPETUS o ?empresa=OIL_GAS
    """
    if not _usuario_puede_ver_cotizaciones(request.user):
        return JsonResponse({"error": "No autorizado"}, status=403)

    empresa = request.GET.get("empresa") or Quotation.Empresa.IMPETUS
    return JsonResponse({
        "empresa": empresa,
        "numero": generar_numero_cotizacion(empresa),
    })


@login_required
def lista_clientes(request):
    if not _usuario_puede_ver_cotizaciones(request.user):
        messages.error(request, "No tienes acceso a Clientes.")
        return redirect("/")

    clientes = Cliente.objects.all()
    return render(request, "quotes/clientes_lista.html", {
        "clientes": clientes,
    })


@login_required
def crear_cliente(request):
    if not _usuario_puede_ver_cotizaciones(request.user):
        messages.error(request, "No tienes acceso a Clientes.")
        return redirect("/")

    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente creado correctamente.")
            return redirect("lista_clientes")
    else:
        form = ClienteForm()

    return render(request, "quotes/cliente_form.html", {
        "form": form,
        "modo": "crear",
    })


@login_required
def editar_cliente(request, pk):
    if not _usuario_puede_ver_cotizaciones(request.user):
        messages.error(request, "No tienes acceso a Clientes.")
        return redirect("/")

    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente actualizado correctamente.")
            return redirect("lista_clientes")
    else:
        form = ClienteForm(instance=cliente)

    return render(request, "quotes/cliente_form.html", {
        "form": form,
        "modo": "editar",
        "cliente": cliente,
    })
