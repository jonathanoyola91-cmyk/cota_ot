from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("/dashboard/")

        messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("/accounts/login/")


@login_required
def perfil_view(request):
    if request.method == "POST":
        user = request.user
        user.first_name = request.POST.get("first_name", "")
        user.last_name = request.POST.get("last_name", "")
        user.email = request.POST.get("email", "")
        user.save()

        messages.success(request, "Perfil actualizado correctamente.")
        return redirect("/accounts/perfil/")

    return render(request, "accounts/perfil.html")