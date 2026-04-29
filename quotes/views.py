from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.roles import tiene_rol
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Max
from .models import Quotation
from .forms import QuotationForm
from django.db.models import Sum
from .models import Quotation


@login_required
def lista_cotizaciones(request):
    if not tiene_rol(request.user, ["COMERCIAL", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes acceso a Cotizaciones.")
        return redirect("/")

    cotizaciones = Quotation.objects.all().order_by("-id")

    return render(request, "quotes/lista.html", {
        "cotizaciones": cotizaciones,
    })

def generar_numero_cotizacion():
    ultimo = Quotation.objects.aggregate(Max("id"))["id__max"] or 0
    siguiente = ultimo + 1
    return f"COT-{siguiente:05d}"


def lista_cotizaciones(request):
    cotizaciones = Quotation.objects.all().order_by("-id")

    total = cotizaciones.count()
    evaluacion = cotizaciones.filter(estado="EVALUACION").count()
    adjudicadas = cotizaciones.filter(estado="ADJUDICADA").count()
    cerradas = cotizaciones.filter(estado="CERRADA").count()

    valor_adjudicado = cotizaciones.filter(
        estado="ADJUDICADA"
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


def crear_cotizacion(request):
    if request.method == "POST":
        form = QuotationForm(request.POST)
        if form.is_valid():
            cotizacion = form.save(commit=False)
            cotizacion.numero_cotizacion = generar_numero_cotizacion()
            cotizacion.save()
            return redirect("detalle_cotizacion", pk=cotizacion.pk)
    else:
        form = QuotationForm()

    return render(request, "quotes/quotation_form.html", {
        "form": form,
        "modo": "crear",
        "numero_preview": generar_numero_cotizacion(),
    })


def editar_cotizacion(request, pk):
    cotizacion = get_object_or_404(Quotation, pk=pk)

    if request.method == "POST":
        form = QuotationForm(request.POST, instance=cotizacion)
        if form.is_valid():
            form.save()
            return redirect("detalle_cotizacion", pk=cotizacion.pk)
    else:
        form = QuotationForm(instance=cotizacion)

    return render(request, "quotes/quotation_form.html", {
        "form": form,
        "modo": "editar",
        "cotizacion": cotizacion,
        "numero_preview": cotizacion.numero_cotizacion,
    })


def detalle_cotizacion(request, pk):
    cotizacion = get_object_or_404(Quotation, pk=pk)

    return render(request, "quotes/detail.html", {
        "cotizacion": cotizacion
    })

from .models import Cliente
from .forms import ClienteForm


def lista_clientes(request):
    clientes = Cliente.objects.all()
    return render(request, "quotes/clientes_lista.html", {
        "clientes": clientes
    })


def crear_cliente(request):
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("lista_clientes")
    else:
        form = ClienteForm()

    return render(request, "quotes/cliente_form.html", {
        "form": form,
        "modo": "crear"
    })


def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect("lista_clientes")
    else:
        form = ClienteForm(instance=cliente)

    return render(request, "quotes/cliente_form.html", {
        "form": form,
        "modo": "editar",
        "cliente": cliente
    })