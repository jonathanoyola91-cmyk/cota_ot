def tiene_rol(user, roles):
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()