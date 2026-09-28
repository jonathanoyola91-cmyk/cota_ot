            messages.success(request, "Mediciones guardadas.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)

    orden_mecanizado = OrdenMecanizadoEje.objects.filter(inspeccion_origen=inspeccion).first()
    return render(request, "taller/metrologia_eje_detalle.html", {
        "inspeccion": inspeccion,
        "mediciones": mediciones,
        "instrumentos": instrumentos,
        "orden_mecanizado": orden_mecanizado,
        "reinspecciones": inspeccion.reinspecciones.order_by("numero_inspeccion"),
    })


@login_required
@transaction.atomic
def metrologia_eje_dictamen(request, inspeccion_id):
    inspeccion = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    if inspeccion.estado == InspeccionEje.Estado.BORRADOR:
        messages.error(request, "Primero debe revisar las mediciones.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)

    # Un dictamen cerrado puede corregirse mientras no haya iniciado el flujo
    # de mecanizado/reinspección. Después se conserva bloqueado como evidencia.
    if inspeccion.estado == InspeccionEje.Estado.CERRADA:
        tiene_orden = OrdenMecanizadoEje.objects.filter(inspeccion_origen=inspeccion).exists()
        tiene_reinspeccion = inspeccion.reinspecciones.exists()
        if tiene_orden or tiene_reinspeccion:
            messages.error(request, "El dictamen ya no puede cambiarse porque existe una orden de mecanizado o una reinspección asociada.")
            return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)

    if request.method == "POST":
        form = DictamenInspeccionEjeForm(request.POST, instance=inspeccion)
        if form.is_valid() and form.cleaned_data["dictamen"] != InspeccionEje.Dictamen.PENDIENTE:
            obj = form.save(commit=False)
            obj.estado = InspeccionEje.Estado.CERRADA
            obj.revisado_por = request.user
            obj.fecha_revision = timezone.now()
            obj.save()
            messages.success(request, "Dictamen de Calidad actualizado.")
            if obj.dictamen == InspeccionEje.Dictamen.MECANIZADO:
                messages.info(request, "La pieza requiere mecanizado. Ya puede crear la orden de mecanizado.")
                return redirect("taller:metrologia_eje_detalle", inspeccion_id=obj.id)
            return redirect("taller:metrologia_eje_reporte", inspeccion_id=obj.id)
    else:
        form = DictamenInspeccionEjeForm(instance=inspeccion)
    return render(request, "taller/metrologia_eje_dictamen.html", {"form": form, "inspeccion": inspeccion})


@login_required
def metrologia_eje_reporte(request, inspeccion_id):
    inspeccion = get_object_or_404(
        InspeccionEje.objects.select_related("paw", "plantilla", "realizado_por", "revisado_por"),
        pk=inspeccion_id,
    )
    mediciones = list(inspeccion.mediciones.select_related("punto", "instrumento").all())
    hay_evidencias = any(bool(m.evidencia) for m in mediciones)
    # Resumen único de los equipos físicos utilizados para trazabilidad metrológica.
    instrumentos_usados = []
    vistos = set()
    for m in mediciones:
        if m.instrumento_id and m.instrumento_id not in vistos:
            vistos.add(m.instrumento_id)
            instrumentos_usados.append(m.instrumento)
    return render(request, "taller/metrologia_eje_reporte.html", {
        "inspeccion": inspeccion,
        "mediciones": mediciones,
        "hay_evidencias": hay_evidencias,
        "instrumentos_usados": instrumentos_usados,
    })

@login_required
@require_POST
@transaction.atomic
def metrologia_mecanizado_crear(request, inspeccion_id):
    inspeccion = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    if inspeccion.estado != InspeccionEje.Estado.CERRADA or inspeccion.dictamen != InspeccionEje.Dictamen.MECANIZADO:
        messages.error(request, "La orden de mecanizado solo puede crearse desde una inspección cerrada con dictamen Requiere mecanizado.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)
    if hasattr(inspeccion, "orden_mecanizado"):
        messages.info(request, "Esta inspección ya tiene una orden de mecanizado.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)
    trabajo = request.POST.get("trabajo_requerido", "").strip()
    if not trabajo:
        messages.error(request, "Describa el trabajo de mecanizado requerido.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)
    OrdenMecanizadoEje.objects.create(
        inspeccion_origen=inspeccion,
        trabajo_requerido=trabajo,
        medida_objetivo=request.POST.get("medida_objetivo", "").strip(),
        responsable=request.user,
        creado_por=request.user,
    )
    messages.success(request, "Orden de mecanizado creada. La inspección original permanece bloqueada como evidencia.")
    return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)


@login_required
@require_POST
@transaction.atomic
def metrologia_mecanizado_terminar(request, inspeccion_id):
    inspeccion = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    orden = get_object_or_404(OrdenMecanizadoEje, inspeccion_origen=inspeccion)
    orden.observaciones_taller = request.POST.get("observaciones_taller", "").strip()
    orden.estado = OrdenMecanizadoEje.Estado.TERMINADO
    orden.terminado_en = timezone.now()
    orden.save(update_fields=["observaciones_taller", "estado", "terminado_en"])
    messages.success(request, "Mecanizado marcado como terminado. Ya puede crear la reinspección.")
    return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)


@login_required
@require_POST
@transaction.atomic
def metrologia_reinspeccion_crear(request, inspeccion_id):
    origen = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    orden = get_object_or_404(OrdenMecanizadoEje, inspeccion_origen=origen)
    if orden.estado != OrdenMecanizadoEje.Estado.TERMINADO:
        messages.error(request, "Primero marque el mecanizado como terminado.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=origen.id)
    existente = origen.reinspecciones.order_by("-numero_inspeccion").first()
    if existente:
        messages.info(request, "Ya existe una reinspección creada para esta inspección.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=existente.id)
    nueva = InspeccionEje.objects.create(
        paw=origen.paw, plantilla=origen.plantilla, camara=origen.camara,
        serial_equipo=origen.serial_equipo, serial_eje=origen.serial_eje, realizado_por=request.user,
        inspeccion_origen=origen, numero_inspeccion=origen.numero_inspeccion + 1,
    )
    for punto in origen.plantilla.puntos.all():
        MedicionEje.objects.create(inspeccion=nueva, punto=punto)
    orden.estado = OrdenMecanizadoEje.Estado.REINSPECCIONADO
    orden.save(update_fields=["estado"])
    messages.success(request, "Reinspección creada. Las mediciones originales se conservaron sin cambios.")
    return redirect("taller:metrologia_eje_detalle", inspeccion_id=nueva.id)
