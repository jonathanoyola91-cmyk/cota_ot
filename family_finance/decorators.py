from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect

from . import family_messages as messages
from .models import FamilyMembership


def family_member_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            membership = request.user.family_membership
        except FamilyMembership.DoesNotExist:
            if request.user.is_superuser:
                return redirect("family_finance:setup")
            raise Http404
        if not membership.active:
            raise Http404
        request.family_membership = membership
        request.household = membership.household
        return view_func(request, *args, **kwargs)

    return wrapped


def manager_required(view_func):
    @family_member_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.family_membership.can_manage:
            messages.error(request, "No tienes permiso para administrar el presupuesto familiar.")
            return redirect("family_finance:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapped


def owner_required(view_func):
    @family_member_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.family_membership.can_approve:
            messages.error(request, "Esta aprobación corresponde al propietario de la familia.")
            return redirect("family_finance:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapped
