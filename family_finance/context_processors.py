from .models import FamilyMembership


def family_access(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"family_access": False, "family_nav_membership": None}
    try:
        membership = request.user.family_membership
    except FamilyMembership.DoesNotExist:
        membership = None
    return {
        "family_access": bool(request.user.is_superuser or (membership and membership.active)),
        "family_nav_membership": membership,
    }

