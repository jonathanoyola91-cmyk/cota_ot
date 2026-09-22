"""Mensajes exclusivos del módulo familiar.

El framework de mensajes de Django comparte una sola cola por sesión. La
etiqueta ``family`` evita que avisos pendientes de Inventario, Compras u otros
módulos se presenten dentro del espacio familiar.
"""

from django.contrib import messages as django_messages


def _send(level_function, request, message, *args, **kwargs):
    extra_tags = kwargs.pop("extra_tags", "")
    kwargs["extra_tags"] = f"{extra_tags} family".strip()
    return level_function(request, message, *args, **kwargs)


def success(request, message, *args, **kwargs):
    return _send(django_messages.success, request, message, *args, **kwargs)


def error(request, message, *args, **kwargs):
    return _send(django_messages.error, request, message, *args, **kwargs)


def warning(request, message, *args, **kwargs):
    return _send(django_messages.warning, request, message, *args, **kwargs)


def info(request, message, *args, **kwargs):
    return _send(django_messages.info, request, message, *args, **kwargs)

