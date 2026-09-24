from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.contrib.staticfiles import finders
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import HSEMovement, HSERequest, HSERequestLine, HSEStock


def _hse_manager(user):
    return user.is_superuser or user.groups.filter(name__in=["INVENTARIO", "GERENCIA", "HSE"]).exists()


def _empleados_impetus():
    """Usuarios activos de IMPETUS, excluyendo integrantes de Familia.

    Ambos módulos comparten la tabla de usuarios. La relación de integrantes
    de Familia se detecta de forma dinámica para no depender de un modelo
    concreto del módulo de presupuesto familiar.
    """
    User = get_user_model()
    empleados = User.objects.filter(is_active=True)

    try:
        familia = apps.get_app_config("family_finance")
    except LookupError:
        return empleados.order_by("first_name", "username")

    ids_familia = set()
    nombres_miembro = ("member", "miembro", "integrante", "familyuser", "family_user")
    for modelo in familia.get_models():
        nombre = modelo.__name__.lower()
        if not any(texto in nombre for texto in nombres_miembro):
            continue
        for campo in modelo._meta.fields:
            if getattr(campo, "remote_field", None) and campo.remote_field.model == User:
                ids_familia.update(
                    modelo.objects.exclude(**{f"{campo.name}__isnull": True})
                    .values_list(f"{campo.name}_id", flat=True)
                )

    return empleados.exclude(pk__in=ids_familia).order_by("first_name", "username")


def _catalog_item(pk):
    # Un formulario puede enviarse antes de seleccionar el resultado del buscador.
    # En ese caso no consultamos la BD con un id vacío.
    if not str(pk or "").isdigit():
        return None
    from item_oil_gas.models import ItemImpetus
    return ItemImpetus.objects.filter(pk=pk, activo=True).first()


@login_required
def dashboard(request):
    # El bloque personal SIEMPRE muestra únicamente lo asignado/solicitado
    # para el usuario conectado. La gestión operativa se presenta aparte.
    propias = (
        HSERequest.objects.filter(empleado=request.user)
        .select_related("empleado", "solicitado_por", "compra")
        .prefetch_related("lineas")
        .order_by("-creado_en")
    )
    es_gestor = _hse_manager(request.user)
    grupos = set(request.user.groups.values_list("name", flat=True))
    es_inventario = request.user.is_superuser or "INVENTARIO" in grupos
    es_gerencia = request.user.is_superuser or "GERENCIA" in grupos
    es_hse = request.user.is_superuser or "HSE" in grupos

    pendientes_entrega = HSERequest.objects.none()
    historial_entregas = HSERequest.objects.none()
    solicitudes_stock = []
    if es_gestor:
        pendientes_entrega = (
            HSERequest.objects.filter(
                estado__in=[HSERequest.Estado.PENDIENTE, HSERequest.Estado.EN_COMPRAS, HSERequest.Estado.LISTA]
            )
            .select_related("empleado", "solicitado_por", "compra")
            .prefetch_related("lineas")
            .order_by("-creado_en")[:12]
        )
        # Historial real de entregas: conserva las solicitudes ya entregadas
        # para que Inventario/HSE/Gerencia puedan auditar a quién, qué y cuánto
        # se entregó, aunque el stock ya haya sido descontado de Bodega HSE.
        historial_entregas = (
            HSERequest.objects.filter(estado=HSERequest.Estado.ENTREGADA)
            .select_related("empleado", "solicitado_por", "entregado_por")
            .prefetch_related("lineas")
            .order_by("-entregado_en", "-pk")[:20]
        )
        # Seguimiento de las reposiciones de bodega creadas por este usuario.
        try:
            from compras_oil.models import PurchaseRequest
            solicitudes_stock = PurchaseRequest.objects.filter(
                origen=PurchaseRequest.Origen.HSE, creado_por=request.user
            ).order_by("-pk")[:20]
        except Exception:
            solicitudes_stock = []

    return render(request, "hse/dashboard.html", {
        "solicitudes": propias,
        "es_gestor": es_gestor,
        "es_inventario": es_inventario,
        "es_gerencia": es_gerencia,
        "es_hse": es_hse,
        "pendientes_entrega": pendientes_entrega,
        "historial_entregas": historial_entregas,
        "solicitudes_stock": solicitudes_stock,
        "stock": HSEStock.objects.order_by("codigo") if es_gestor else HSEStock.objects.none(),
    })


@login_required
def entregas_pendientes(request):
    """Ruta operativa para Inventario/HSE: revisar y entregar EPP/dotación."""
    if not _hse_manager(request.user):
        messages.error(request, "No tienes permiso para gestionar entregas HSE.")
        return redirect("hse:dashboard")
    solicitudes = (
        HSERequest.objects
        .filter(estado__in=[HSERequest.Estado.PENDIENTE, HSERequest.Estado.EN_COMPRAS, HSERequest.Estado.LISTA])
        .select_related("empleado", "solicitado_por")
        .prefetch_related("lineas")
        .order_by("-creado_en")
    )
    return render(request, "hse/entregas_pendientes.html", {"solicitudes": solicitudes})



@login_required
def historial_entregas(request):
    """Historial auditable de EPP/dotación entregados a empleados."""
    if not _hse_manager(request.user):
        messages.error(request, "No tienes permiso para consultar el historial HSE.")
        return redirect("hse:dashboard")

    solicitudes = (
        HSERequest.objects.filter(estado=HSERequest.Estado.ENTREGADA)
        .select_related("empleado", "solicitado_por", "entregado_por")
        .prefetch_related("lineas")
        .order_by("-entregado_en", "-pk")
    )

    q = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()
    if q:
        solicitudes = solicitudes.filter(
            Q(empleado__first_name__icontains=q)
            | Q(empleado__last_name__icontains=q)
            | Q(empleado__username__icontains=q)
            | Q(lineas__codigo__icontains=q)
            | Q(lineas__descripcion__icontains=q)
        ).distinct()
    if tipo in {HSERequest.Tipo.EPP, HSERequest.Tipo.DOTACION}:
        solicitudes = solicitudes.filter(tipo=tipo)

    return render(request, "hse/historial_entregas.html", {
        "solicitudes": solicitudes,
        "q": q,
        "tipo": tipo,
    })


@login_required
def buscar_items(request):
    q = (request.GET.get("q") or "").strip()
    tipo = request.GET.get("tipo")
    # Para Stock/EPP se permite consulta vacía: el selector carga de inmediato
    # los P/N EPP activos del catálogo IMPETUS.
    if len(q) < 2 and tipo != HSERequest.Tipo.EPP:
        return JsonResponse({"results": []})
    from item_oil_gas.models import ItemImpetus
    # HSE usa exclusivamente el catálogo de artículos IMPETUS HPS.
    qs = ItemImpetus.objects.filter(activo=True).filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    if tipo == HSERequest.Tipo.EPP:
        qs = qs.filter(codigo__istartswith="EPP")
    return JsonResponse({"results": [{"id": x.pk, "codigo": x.codigo, "descripcion": x.descripcion, "unidad": x.unidad_medida or "UND", "label": f"{x.codigo} - {x.descripcion}"} for x in qs.order_by("codigo")[:20]]})


@login_required
def solicitar(request, tipo):
    if tipo not in HSERequest.Tipo.values:
        return redirect("hse:dashboard")
    # Dotación sólo puede ser solicitada por Gerencia/HSE; EPP lo solicita cualquier colaborador.
    if tipo == HSERequest.Tipo.DOTACION and not _hse_manager(request.user):
        messages.error(request, "La solicitud de dotación semestral debe ser creada por Gerencia o HSE.")
        return redirect("hse:dashboard")
    empleados = _empleados_impetus()
    if request.method == "POST":
        empleado_id = request.POST.get("empleado") if tipo == HSERequest.Tipo.DOTACION else request.user.pk
        empleado = empleados.filter(pk=empleado_id).first()
        ids, cantidades = request.POST.getlist("item_id"), request.POST.getlist("cantidad")
        filas = []
        for i, item_id in enumerate(ids):
            if not str(item_id).isdigit():
                continue
            item = _catalog_item(item_id)
            try: cantidad = Decimal((cantidades[i] if i < len(cantidades) else "0").replace(",", "."))
            except Exception: cantidad = Decimal("0")
            if item and cantidad > 0:
                filas.append((item, cantidad))
        if not empleado or not filas:
            messages.error(request, "Selecciona el empleado y al menos un P/N con cantidad válida.")
        else:
            with transaction.atomic():
                motivo = request.POST.get("motivo_entrega") or HSERequest.MotivoEntrega.PRIMERA
                if tipo != HSERequest.Tipo.EPP or motivo not in HSERequest.MotivoEntrega.values:
                    motivo = HSERequest.MotivoEntrega.PRIMERA
                sol = HSERequest.objects.create(tipo=tipo, empleado=empleado, solicitado_por=request.user, observacion=(request.POST.get("observacion") or "").strip(), motivo_entrega=motivo)
                HSERequestLine.objects.bulk_create([HSERequestLine(solicitud=sol, catalogo="IMPETUS", catalogo_item_id=i.pk, codigo=i.codigo or "", descripcion=i.descripcion or "", unidad=i.unidad_medida or "UND", cantidad_solicitada=c) for i, c in filas])
            messages.success(request, f"Solicitud {sol.codigo} enviada a Inventario.")
            return redirect("hse:detalle", pk=sol.pk)
    return render(request, "hse/solicitud_form.html", {"tipo": tipo, "empleados": empleados})


@login_required
def editar_solicitud(request, pk):
    """Edita una solicitud HSE conservando el mismo consecutivo.

    Por decisión operativa, no se bloquea por estado de Compras. Si ya existe
    una PurchaseRequest asociada, se sincronizan sus líneas con los faltantes
    actuales para evitar crear otra compra.
    """
    sol = get_object_or_404(HSERequest.objects.prefetch_related("lineas"), pk=pk)
    if sol.empleado_id != request.user.id and not _hse_manager(request.user):
        messages.error(request, "No tienes permiso para modificar esta solicitud.")
        return redirect("hse:dashboard")
    empleados = _empleados_impetus()
    if request.method == "POST":
        empleado_id = request.POST.get("empleado") if sol.tipo == HSERequest.Tipo.DOTACION else sol.empleado_id
        empleado = empleados.filter(pk=empleado_id).first()
        ids, cantidades = request.POST.getlist("item_id"), request.POST.getlist("cantidad")
        filas = []
        for i, item_id in enumerate(ids):
            item = _catalog_item(item_id)
            try:
                cantidad = Decimal((cantidades[i] if i < len(cantidades) else "0").replace(",", "."))
            except Exception:
                cantidad = Decimal("0")
            if item and cantidad > 0:
                filas.append((item, cantidad))
        if not empleado or not filas:
            messages.error(request, "Selecciona al menos un P/N con cantidad válida.")
        else:
            with transaction.atomic():
                sol.empleado = empleado
                sol.observacion = (request.POST.get("observacion") or "").strip()
                motivo = request.POST.get("motivo_entrega") or sol.motivo_entrega
                if sol.tipo == HSERequest.Tipo.EPP and motivo in HSERequest.MotivoEntrega.values:
                    sol.motivo_entrega = motivo
                sol.save()
                sol.lineas.all().delete()
                HSERequestLine.objects.bulk_create([
                    HSERequestLine(solicitud=sol, catalogo="IMPETUS", catalogo_item_id=item.pk,
                                   codigo=item.codigo or "", descripcion=item.descripcion or "",
                                   unidad=item.unidad_medida or "UND", cantidad_solicitada=cantidad)
                    for item, cantidad in filas
                ])
                if sol.compra_id:
                    from compras_oil.models import PurchaseLine
                    PurchaseLine.objects.filter(request_id=sol.compra_id).delete()
                    nuevas = []
                    for item, cantidad in filas:
                        stock = HSEStock.objects.filter(catalogo="IMPETUS", catalogo_item_id=item.pk).first()
                        disponible = Decimal(stock.cantidad_fisica or 0) if stock else Decimal("0")
                        faltante = max(Decimal("0"), cantidad - disponible)
                        if faltante > 0:
                            nuevas.append(PurchaseLine(request_id=sol.compra_id, codigo=item.codigo or "",
                                descripcion=item.descripcion or "", unidad=item.unidad_medida or "UND",
                                cantidad_requerida=faltante))
                    if nuevas:
                        PurchaseLine.objects.bulk_create(nuevas)
            messages.success(request, f"Solicitud {sol.codigo} actualizada.")
            return redirect("hse:detalle", pk=sol.pk)
    return render(request, "hse/solicitud_editar.html", {"solicitud": sol, "empleados": empleados})


@login_required
def reponer_bodega(request):
    """Compra preventiva de EPP: no requiere asignarlo aún a un colaborador."""
    if not _hse_manager(request.user):
        messages.error(request, "Sólo Inventario, HSE o Gerencia pueden reponer Bodega HSE.")
        return redirect("hse:dashboard")
    if request.method == "POST":
        item = _catalog_item(request.POST.get("item_id"))
        try: cantidad = Decimal((request.POST.get("cantidad") or "0").replace(",", "."))
        except Exception: cantidad = Decimal("0")
        if not item or cantidad <= 0 or not (item.codigo or "").upper().startswith("EPP"):
            messages.error(request, "Selecciona un P/N EPP y una cantidad válida.")
        else:
            from compras_oil.models import PurchaseLine, PurchaseRequest
            compra = PurchaseRequest.objects.create(origen=PurchaseRequest.Origen.HSE, empresa_destino=PurchaseRequest.EmpresaDestino.IMPETUS, motivo_stock=f"Reposición preventiva Bodega HSE · {item.codigo}", inventario_revisado_en=timezone.now(), inventario_revisado_por=request.user, creado_por=request.user, paw_nombre="Bodega HSE")
            PurchaseLine.objects.create(request=compra, codigo=item.codigo or "", descripcion=item.descripcion or "", unidad=item.unidad_medida or "UND", cantidad_requerida=cantidad, cantidad_a_comprar=cantidad)
            messages.success(request, "Reposición HSE enviada a Compras.")
            return redirect("compras_oil:paw_detail", pk=compra.pk)
    return render(request, "hse/reposicion_form.html")


@login_required
def carga_inicial(request):
    """Ingreso de existencias físicas actuales a Bodega HSE, sin contabilidad."""
    if not _hse_manager(request.user):
        messages.error(request, "Sólo Inventario, HSE o Gerencia pueden cargar Bodega HSE.")
        return redirect("hse:dashboard")
    if request.method == "POST":
        ids, cantidades = request.POST.getlist("item_id"), request.POST.getlist("cantidad")
        movimientos = []
        with transaction.atomic():
            for indice, item_id in enumerate(ids):
                item = _catalog_item(item_id)
                try:
                    cantidad = Decimal((cantidades[indice] if indice < len(cantidades) else "0").replace(",", "."))
                except Exception:
                    cantidad = Decimal("0")
                if not item or cantidad <= 0 or not (item.codigo or "").upper().startswith("EPP"):
                    continue
                stock, _ = HSEStock.objects.select_for_update().get_or_create(
                    catalogo="IMPETUS", catalogo_item_id=item.pk,
                    defaults={"codigo": item.codigo or "", "descripcion": item.descripcion or "", "unidad": item.unidad_medida or "UND"},
                )
                anterior = Decimal(stock.cantidad_fisica or 0)
                stock.cantidad_fisica = anterior + cantidad
                stock.save(update_fields=["cantidad_fisica", "actualizado_en"])
                movimientos.append(HSEMovement(stock=stock, tipo=HSEMovement.Tipo.AJUSTE, cantidad=cantidad, saldo_anterior=anterior, saldo_nuevo=stock.cantidad_fisica, referencia="HSE-INICIAL", creado_por=request.user))
            if movimientos:
                HSEMovement.objects.bulk_create(movimientos)
        if not movimientos:
            messages.error(request, "Agrega al menos un P/N EPP válido con cantidad mayor que cero.")
        else:
            messages.success(request, f"Carga inicial HSE registrada: {len(movimientos)} ítem(s). No afectó el inventario contable.")
            return redirect("hse:dashboard")
    return render(request, "hse/carga_inicial.html")


@login_required
def detalle(request, pk):
    sol = get_object_or_404(HSERequest.objects.select_related("empleado", "solicitado_por", "compra").prefetch_related("lineas"), pk=pk)
    if sol.empleado_id != request.user.id and not _hse_manager(request.user):
        messages.error(request, "No tienes permiso para ver esta solicitud.")
        return redirect("hse:dashboard")
    return render(request, "hse/detalle.html", {"solicitud": sol, "es_gestor": _hse_manager(request.user)})


@login_required
def procesar_inventario(request, pk):
    if not _hse_manager(request.user) or request.method != "POST":
        return redirect("hse:dashboard")
    sol = get_object_or_404(HSERequest.objects.prefetch_related("lineas"), pk=pk)
    if sol.estado not in [HSERequest.Estado.PENDIENTE, HSERequest.Estado.EN_COMPRAS]:
        messages.error(request, "La solicitud ya fue cerrada.")
        return redirect("hse:detalle", pk=pk)
    faltantes = []
    for linea in sol.lineas.all():
        stock = HSEStock.objects.filter(catalogo=linea.catalogo, catalogo_item_id=linea.catalogo_item_id).first()
        disponible = Decimal(stock.cantidad_fisica or 0) if stock else Decimal("0")
        if disponible < Decimal(linea.cantidad_solicitada):
            faltantes.append((linea, Decimal(linea.cantidad_solicitada) - disponible))
    if not faltantes:
        sol.estado = HSERequest.Estado.LISTA
        sol.save(update_fields=["estado", "actualizado_en"])
        messages.success(request, "Hay disponibilidad en Bodega HSE. La solicitud quedó lista para entregar.")
    else:
        from compras_oil.models import PurchaseLine, PurchaseRequest
        with transaction.atomic():
            # La relación con HSE vive en HSERequest.compra.
            # ``solicitud_hse`` es el related_name inverso y NO un campo
            # de PurchaseRequest, por lo que no puede usarse en create/get_or_create.
            if sol.compra_id:
                compra = sol.compra
            else:
                compra = PurchaseRequest.objects.create(
                    origen=PurchaseRequest.Origen.HSE,
                    empresa_destino=PurchaseRequest.EmpresaDestino.IMPETUS,
                    motivo_stock=f"{sol.codigo} · {sol.nombre_formato} para {sol.empleado.get_full_name() or sol.empleado.username}",
                    inventario_revisado_en=timezone.now(),
                    inventario_revisado_por=request.user,
                    creado_por=request.user,
                    paw_nombre=sol.codigo,
                )
            for linea, faltante in faltantes:
                PurchaseLine.objects.get_or_create(request=compra, codigo=linea.codigo, defaults={"descripcion": linea.descripcion, "unidad": linea.unidad, "cantidad_requerida": faltante})
            sol.compra = compra
            sol.estado = HSERequest.Estado.EN_COMPRAS
            sol.save(update_fields=["compra", "estado", "actualizado_en"])
        messages.info(request, f"Faltantes de {sol.codigo} enviados a Compras. Al recibirlos entrarán a Bodega HSE.")
        return redirect("compras_oil:paw_detail", pk=sol.compra_id)
    return redirect("hse:detalle", pk=pk)


@login_required
def entregar(request, pk):
    if not _hse_manager(request.user) or request.method != "POST":
        return redirect("hse:dashboard")
    sol = get_object_or_404(HSERequest.objects.prefetch_related("lineas"), pk=pk)
    if sol.estado != HSERequest.Estado.LISTA:
        messages.error(request, "Primero verifica disponibilidad o recibe los faltantes en Bodega HSE.")
        return redirect("hse:detalle", pk=pk)
    with transaction.atomic():
        for linea in sol.lineas.select_for_update():
            stock = HSEStock.objects.select_for_update().filter(catalogo=linea.catalogo, catalogo_item_id=linea.catalogo_item_id).first()
            cantidad = Decimal(linea.cantidad_solicitada)
            if not stock or Decimal(stock.cantidad_fisica) < cantidad:
                messages.error(request, f"Stock insuficiente de {linea.codigo}. Revisa Bodega HSE.")
                return redirect("hse:detalle", pk=pk)
            anterior = Decimal(stock.cantidad_fisica)
            stock.cantidad_fisica = anterior - cantidad
            stock.save(update_fields=["cantidad_fisica", "actualizado_en"])
            linea.cantidad_entregada = cantidad
            linea.save(update_fields=["cantidad_entregada"])
            HSEMovement.objects.create(stock=stock, tipo=HSEMovement.Tipo.ENTREGA, cantidad=-cantidad, saldo_anterior=anterior, saldo_nuevo=stock.cantidad_fisica, referencia=sol.codigo, creado_por=request.user)
        sol.estado, sol.entregado_en, sol.entregado_por = HSERequest.Estado.ENTREGADA, timezone.now(), request.user
        sol.save(update_fields=["estado", "entregado_en", "entregado_por", "actualizado_en"])
    messages.success(request, "Entrega registrada y formato disponible para el empleado.")
    return redirect("hse:pdf", pk=pk)


def _texto(valor, styles):
    return Paragraph(escape(str(valor or "")), styles["Normal"])


def _texto_centrado(valor, styles, negrita=True):
    estilo = styles["Normal"].clone("hse_centrado")
    estilo.alignment = 1
    if negrita:
        estilo.fontName = "Helvetica-Bold"
    return Paragraph(escape(str(valor or "")), estilo)


def _logo_impetus():
    """Logo corporativo usado también en las remisiones de Inventario."""
    ruta = finders.find("img/logo_empresa.png")
    return Image(str(ruta), width=92, height=48, kind="proportional") if ruta else "IMPETUS HPS"


def _encabezado(story, styles, codigo, titulo, version, fecha=""):
    derecha = [_texto(f"Código: {codigo}", styles), _texto(f"Versión: {version}", styles)]
    if fecha:
        derecha += [_texto(f"Fecha: {fecha}", styles), _texto("Pág. 1 de 1", styles)]
    tabla = Table([[_logo_impetus(), _texto_centrado("SISTEMA DE GESTIÓN DE SEGURIDAD Y SALUD EN EL TRABAJO", styles), derecha]], colWidths=[100, 315, 137])
    tabla.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .7, colors.black), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    titulo_t = Table([[_texto_centrado(titulo, styles)]], colWidths=[552])
    titulo_t.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .7, colors.black), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
    story.extend([tabla, titulo_t, Spacer(1, 7)])


def _formato_hse(sol, styles):
    nombre = sol.empleado.get_full_name() or sol.empleado.username
    fecha = timezone.localtime(sol.entregado_en).strftime("%d/%m/%Y")
    es_dotacion = sol.tipo == HSERequest.Tipo.DOTACION
    story = []
    _encabezado(story, styles, "SST-FOR-023" if es_dotacion else "SST-FOR-025", "ENTREGA DE DOTACIÓN" if es_dotacion else "FORMATO ENTREGA DE ELEMENTOS DE PROTECCIÓN PERSONAL", "1" if es_dotacion else "01", "16/04/2026" if not es_dotacion else "")
    datos = Table([[_texto(f"NOMBRE DEL EMPLEADO: {nombre}", styles)], [_texto("CARGO: ______________________________", styles)]], colWidths=[552])
    datos.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .6, colors.black), ("INNERGRID", (0,0), (-1,-1), .5, colors.black), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story += [datos, Spacer(1, 6)]
    if not es_dotacion:
        compromiso = "He recibido de IMPETUS HPS los elementos de protección personal (EPP) correspondientes a mi cargo. Me comprometo a utilizarlos adecuadamente, mantenerlos en buen estado e informar su deterioro o pérdida para su reposición, cumpliendo las normas de seguridad y salud en el trabajo."
        bloque = Table([[_texto("COMPROMISO", styles)], [_texto(compromiso, styles)], [_texto("FIRMA ACEPTACIÓN COMPROMISO", styles)]], colWidths=[552])
        bloque.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .6, colors.black), ("INNERGRID", (0,0), (-1,-1), .5, colors.black), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E7E6E6")), ("TOPPADDING", (0,2), (-1,2), 16)]))
        story += [bloque, Spacer(1, 6)]
        filas = [["FECHA", "ELEMENTO", "CANT.", "TALLA", "MOTIVO", "FIRMA TRABAJADOR"]]
        motivo = sol.get_motivo_entrega_display()
        for l in sol.lineas.all(): filas.append([fecha, _texto(f"{l.codigo} - {l.descripcion}", styles), str(l.cantidad_entregada.normalize()), "", motivo, ""])
        # 17 renglones de detalle (incluido lo entregado) mantienen el formato en una sola hoja.
        while len(filas) < 18: filas.append(["", "", "", "", "", ""])
        anchos = [60, 210, 48, 45, 85, 104]
        nota = "Una vez diligenciado, este formato debe ser digitalizado y archivado en SST y TH."
    else:
        filas = [["CANT", "DESCRIPCIÓN", "TALLA", "FIRMA DEL EMPLEADO", "FIRMA QUIEN ENTREGA", "FECHA"]]
        for l in sol.lineas.all(): filas.append([str(l.cantidad_entregada.normalize()), _texto(f"{l.codigo} - {l.descripcion}", styles), "", "", "", fecha])
        # Dotación suele contener pocos ítems; se reservan renglones sin forzar una segunda hoja.
        while len(filas) < 18: filas.append(["", "", "", "", "", ""])
        anchos = [42, 192, 48, 105, 105, 60]
        nota = "El buen uso de estos elementos es obligatorio. Cualquier daño o pérdida por descuido deberá ser reportado y asumido conforme al reglamento interno de trabajo."
    tabla = Table(filas, colWidths=anchos, repeatRows=1, rowHeights=[17] * len(filas))
    tabla.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D9EAD3")), ("GRID", (0,0), (-1,-1), .5, colors.black), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 7), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ALIGN", (0,0), (-1,-1), "CENTER")]))
    pie = Table([[_texto(nota + f" Registro interno: {sol.codigo}", styles)]], colWidths=[552])
    pie.setStyle(TableStyle([("BOX", (0,0), (-1,-1), .6, colors.black), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story += [tabla]
    if not es_dotacion:
        entregador = sol.entregado_por.get_full_name() if sol.entregado_por else ""
        firma = Table([["________________________________________"], ["FIRMA QUIEN ENTREGA - INVENTARIO"], [_texto(entregador, styles)]], colWidths=[552])
        firma.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER"), ("TOPPADDING", (0,0), (-1,0), 14), ("FONTSIZE", (0,0), (-1,-1), 8)]))
        story += [Spacer(1, 7), firma]
    story += [Spacer(1, 6), pie]
    return story


@login_required
def comprobante_pdf(request, pk):
    sol = get_object_or_404(HSERequest.objects.select_related("empleado", "solicitado_por", "entregado_por").prefetch_related("lineas"), pk=pk)
    if sol.empleado_id != request.user.id and not _hse_manager(request.user):
        return redirect("hse:dashboard")
    if sol.estado != HSERequest.Estado.ENTREGADA:
        messages.error(request, "El formato se genera al confirmar la entrega.")
        return redirect("hse:detalle", pk=pk)
    buffer = BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=30, rightMargin=30, topMargin=22, bottomMargin=22)
    styles = getSampleStyleSheet(); styles["Normal"].fontSize = 8; styles["Normal"].leading = 10
    doc.build(_formato_hse(sol, styles))
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{sol.codigo}.pdf"'
    return response

@login_required
def editar_solicitud_stock(request, pk):
    """Edita una reposición HSE ya enviada a Compras sin crear otra solicitud."""
    if not _hse_manager(request.user):
        messages.error(request, "No tienes permiso para editar solicitudes de stock HSE.")
        return redirect("hse:dashboard")

    from compras_oil.models import PurchaseLine, PurchaseRequest
    compra = get_object_or_404(PurchaseRequest, pk=pk, origen=PurchaseRequest.Origen.HSE)

    # Conserva la visibilidad actual: el creador puede editar sus solicitudes;
    # los gestores HSE mantienen la capacidad operativa ya existente.
    lineas = PurchaseLine.objects.filter(request=compra).order_by("pk")

    if request.method == "POST":
        codigos = request.POST.getlist("codigo_existente")
        cantidades = request.POST.getlist("cantidad_existente")
        with transaction.atomic():
            actuales = {str(x.codigo): x for x in PurchaseLine.objects.filter(request=compra)}
            for i, codigo in enumerate(codigos):
                linea = actuales.get(str(codigo))
                if not linea:
                    continue
                try:
                    cantidad = Decimal((cantidades[i] if i < len(cantidades) else "0").replace(",", "."))
                except Exception:
                    cantidad = Decimal("0")
                if cantidad <= 0:
                    linea.delete()
                else:
                    # Las reposiciones HSE son solicitudes directas de compra.
                    # Si HSE cambia la cantidad, sincronizamos también la cantidad
                    # real a comprar para evitar que Compras conserve el valor anterior.
                    linea.cantidad_requerida = cantidad
                    linea.cantidad_a_comprar = cantidad
                    linea.save(update_fields=["cantidad_requerida", "cantidad_a_comprar"])

            item = _catalog_item(request.POST.get("item_id"))
            try:
                cantidad_nueva = Decimal((request.POST.get("cantidad_nueva") or "0").replace(",", "."))
            except Exception:
                cantidad_nueva = Decimal("0")
            if item and cantidad_nueva > 0:
                existente = PurchaseLine.objects.filter(request=compra, codigo=item.codigo or "").first()
                if existente:
                    nueva_cantidad = Decimal(existente.cantidad_requerida or 0) + cantidad_nueva
                    existente.cantidad_requerida = nueva_cantidad
                    existente.cantidad_a_comprar = nueva_cantidad
                    existente.save(update_fields=["cantidad_requerida", "cantidad_a_comprar"])
                else:
                    PurchaseLine.objects.create(
                        request=compra, codigo=item.codigo or "", descripcion=item.descripcion or "",
                        unidad=item.unidad_medida or "UND", cantidad_requerida=cantidad_nueva,
                        cantidad_a_comprar=cantidad_nueva
                    )
        messages.success(request, f"Solicitud de stock #{compra.pk} actualizada. Se conserva la misma solicitud en Compras.")
        return redirect("hse:editar_stock", pk=compra.pk)

    return render(request, "hse/reposicion_editar.html", {"compra": compra, "lineas": lineas})
