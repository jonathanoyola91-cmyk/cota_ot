from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

COSTOS_GROUP = 'COSTOS Y PRICING'

def user_can_access_costos(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=COSTOS_GROUP).exists()

def costos_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user_can_access_costos(request.user):
            raise PermissionDenied('No tiene autorización para acceder al Centro de Costos.')
        return view_func(request, *args, **kwargs)
    return _wrapped
