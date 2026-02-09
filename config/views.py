from django.shortcuts import redirect, render

def home(request):
    # Si el usuario ya está autenticado (admin), lo mandamos directo al admin
    if request.user.is_authenticated:
        return redirect("/admin/")
    # Si no, mostramos landing
    return render(request, "home.html")
