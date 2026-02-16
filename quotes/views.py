from django.shortcuts import render, redirect
from .forms import QuotationForm

def crear_cotizacion(request):
    if request.method == "POST":
        form = QuotationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("crear_cotizacion")
    else:
        form = QuotationForm()

    return render(request, "quotes/quotation_form.html", {"form": form})