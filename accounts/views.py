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
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            if hasattr(user, "family_membership") and not user.is_staff and not user.groups.exists():
                return redirect("/familia/")
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
