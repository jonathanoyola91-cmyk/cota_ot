def obtener_ip(request):
    if not request:
        return None

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def registrar_movimiento(
    *,
    request=None,
    usuario=None,
    paw_numero="",
    modulo="",
    accion="",
    descripcion="",
    objeto=None,
    objeto_tipo="",
    objeto_id=None,
    datos_anteriores=None,
    datos_nuevos=None,
):
    from .models import MovimientoSistema

    if request is not None and usuario is None:
        usuario = getattr(request, "user", None)
        if usuario is not None and not usuario.is_authenticated:
            usuario = None

    if objeto is not None:
        objeto_tipo = objeto.__class__.__name__
        objeto_id = getattr(objeto, "pk", None)

    user_agent = ""
    ip = None
    if request is not None:
        ip = obtener_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:1000]

    return MovimientoSistema.objects.create(
        paw_numero=str(paw_numero or ""),
        modulo=str(modulo or "")[:50],
        accion=str(accion or "")[:150],
        descripcion=descripcion or "",
        usuario=usuario,
        objeto_tipo=str(objeto_tipo or "")[:80],
        objeto_id=objeto_id,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        ip=ip,
        user_agent=user_agent,
    )
