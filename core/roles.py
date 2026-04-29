from django.shortcuts import redirect
from django.contrib import messages


def tiene_rol(user, roles):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return user.groups.filter(name__in=roles).exists()


def rol_requerido(roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not tiene_rol(request.user, roles):
                messages.error(request, "No tienes permiso para acceder a este módulo.")
                return redirect("/dashboard/")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator