from decimal import Decimal
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone
from django.utils.timezone import localdate
from compras_oil.models import PurchaseLine
from inventario.models import InventoryStock
from .forms import PriceCalculationForm, PriceLineForm, OperationalCostForm, LaborRateForm, BankTestRateForm, ConsumablesPolicyForm, CifConfigForm, CifItemForm
from .models import PriceCalculation, PriceCalculationLine, OperationalCost, LaborRate, LaborRateHistory, BankTestRate, BankTestRateHistory, ConsumablesPolicy, ConsumablesPolicyHistory, CifConfig, CifItem, CifConfigHistory
from .access import costos_required


def _suggest_cost(item):
    if not item:
        return Decimal('0'), 'Manual', 'COP'

    # 1) Una cotización vigente de Compras tiene prioridad para un precio nuevo.
    if Decimal(item.costo_cotizado or 0) > 0:
        vigente = not item.costo_cotizado_vigente_hasta or item.costo_cotizado_vigente_hasta >= localdate()
        if vigente:
            fecha = item.costo_cotizado_fecha.strftime('%d/%m/%Y') if item.costo_cotizado_fecha else 'sin fecha'
            prov = f' · {item.costo_cotizado_proveedor}' if item.costo_cotizado_proveedor else ''
            return Decimal(item.costo_cotizado), f'Cotización Compras {fecha}{prov}', item.costo_cotizado_moneda or 'COP'

    # 2) Si no hay cotización vigente, usa costo promedio real de inventario.
    stock = InventoryStock.objects.filter(empresa='IMPETUS', catalogo_item_id=item.pk, costo_promedio__gt=0).order_by('-actualizado_en').first()
    if stock:
        return Decimal(stock.costo_promedio), 'Costo promedio Inventario IMPETUS', 'COP'

    # 3) Último respaldo: promedio histórico de compras.
    lines = PurchaseLine.objects.filter(codigo__iexact=item.codigo, precio_unitario__gt=0, cantidad_a_comprar__gt=0).order_by('request__creado_en','pk')
    qty=Decimal('0'); value=Decimal('0')
    for l in lines:
        q=Decimal(l.cantidad_a_comprar or 0); p=Decimal(l.precio_unitario or 0)
        if q>0 and p>0: qty+=q; value+=q*p
    if qty>0:
        return (value/qty).quantize(Decimal('0.01')), 'Promedio histórico de Compras', 'COP'
    return Decimal('0'), 'Sin costo registrado', 'COP'


@costos_required
def buscar_items(request):
    q=(request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    items=(
        __import__('item_oil_gas.models', fromlist=['ItemImpetus']).ItemImpetus.objects
        .filter(activo=True)
        .filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
        .order_by('codigo')[:20]
    )
    results=[]
    for item in items:
        costo, fuente, moneda=_suggest_cost(item)
        results.append({
            'id': item.pk,
            'codigo': item.codigo,
            'descripcion': item.descripcion,
            'costo': str(costo),
            'fuente': fuente,
            'moneda': moneda,
        })
    return JsonResponse({'results': results})

@costos_required
def centro_costos(request):
    return render(request, 'pricing/centro_costos.html')


@costos_required
def lista(request):
    q=(request.GET.get('q') or '').strip()
    qs=PriceCalculation.objects.select_related('item_venta','creado_por','publicado_por')
    if q: qs=qs.filter(Q(item_venta__codigo__icontains=q)|Q(item_venta__descripcion__icontains=q))
    return render(request,'pricing/lista.html',{'calculos':qs[:100],'q':q})

@costos_required
def crear(request):
    form=PriceCalculationForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        obj=form.save(commit=False); obj.creado_por=request.user; obj.save()
        messages.success(request,'Cálculo creado. Ahora agregue los componentes y costos.')
        return redirect('pricing:detalle',pk=obj.pk)
    return render(request,'pricing/crear.html',{'form':form})

@costos_required
def detalle(request,pk):
    calc=get_object_or_404(PriceCalculation.objects.select_related('item_venta'),pk=pk)
    line_form=PriceLineForm()
    return render(request,'pricing/detalle.html',{'calc':calc,'line_form':line_form,'operational_form':OperationalCostForm()})

@costos_required
def agregar_linea(request,pk):
    calc=get_object_or_404(PriceCalculation,pk=pk)
    if calc.estado==PriceCalculation.Estado.PUBLICADO:
        messages.error(request,'Este cálculo ya fue publicado y quedó cerrado como histórico.')
        return redirect('pricing:detalle',pk=pk)
    form=PriceLineForm(request.POST)
    if form.is_valid():
        line=form.save(commit=False); line.calculo=calc
        if line.item_id and Decimal(line.costo_unitario or 0)==0:
            line.costo_unitario,line.fuente_costo,line.moneda=_suggest_cost(line.item)
        elif Decimal(line.costo_unitario or 0)>0:
            line.fuente_costo='Manual / confirmado por usuario'
        
        if Decimal(line.costo_unitario or 0) == 0 and line.costo_cero_justificado and not (line.motivo_costo_cero or '').strip():
            messages.error(request,'Si marca Sin costo / incluido, debe indicar el motivo.')
            return redirect('pricing:detalle',pk=pk)
        line.save(); messages.success(request,f'Costo agregado: {line.descripcion}.')
    else:
        messages.error(request,'Revise los datos del costo. ' + ' '.join(sum(form.errors.values(), [])))
    return redirect('pricing:detalle',pk=pk)

@costos_required
def eliminar_linea(request,pk,line_id):
    calc=get_object_or_404(PriceCalculation,pk=pk)
    if request.method=='POST' and calc.estado==PriceCalculation.Estado.BORRADOR:
        get_object_or_404(calc.lineas,pk=line_id).delete(); messages.success(request,'Línea eliminada.')
    return redirect('pricing:detalle',pk=pk)

@costos_required
def actualizar_costo_linea(request,pk,line_id):
    calc=get_object_or_404(PriceCalculation,pk=pk)
    line=get_object_or_404(calc.lineas,pk=line_id)
    if request.method=='POST' and calc.estado==PriceCalculation.Estado.BORRADOR and line.item_id:
        costo, fuente, moneda = _suggest_cost(line.item)
        line.costo_unitario=costo; line.fuente_costo=fuente; line.moneda=moneda
        if costo > 0:
            line.costo_cero_justificado=False; line.motivo_costo_cero=''
        line.save()
        messages.success(request,f'Costo actualizado: {line.codigo} = ${costo:,.0f}.')
    return redirect('pricing:detalle',pk=pk)

@costos_required
def agregar_costo_operativo(request,pk):
    calc=get_object_or_404(PriceCalculation,pk=pk)
    if request.method=='POST' and calc.estado==PriceCalculation.Estado.BORRADOR:
        form=OperationalCostForm(request.POST)
        if form.is_valid():
            obj=form.save(commit=False); obj.calculo=calc; obj.revisado=True
            if obj.tipo == OperationalCost.Tipo.MANO_OBRA and obj.recurso_mod_id:
                obj.tarifa_unitaria = obj.recurso_mod.costo_hora
                obj.tarifa_origen_nombre = obj.recurso_mod.nombre
                if not obj.descripcion:
                    obj.descripcion = obj.recurso_mod.nombre
            elif obj.tipo == OperationalCost.Tipo.BANCO and obj.aplica:
                banco = BankTestRate.objects.filter(activo=True).order_by('-actualizado_en').first()
                if not banco or banco.costo_hora <= 0:
                    messages.error(request,'Configure primero la tarifa del Banco de prueba / QA-QC.')
                    return redirect('pricing:detalle',pk=pk)
                obj.tarifa_unitaria = banco.costo_hora
                obj.tarifa_origen_nombre = banco.nombre + (' · Completa' if banco.configuracion_completa else ' · PROVISIONAL')
                if not obj.descripcion:
                    obj.descripcion = banco.nombre
            elif obj.tipo == OperationalCost.Tipo.CONSUMIBLES and obj.aplica:
                politica = ConsumablesPolicy.objects.filter(activo=True).order_by('-actualizado_en').first()
                if politica and politica.metodo != ConsumablesPolicy.Metodo.MANUAL:
                    valor = politica.calcular(calc)
                    if valor <= 0:
                        messages.error(request,'La política de Consumibles genera $0. Revise la configuración o cargue primero la MOD.')
                        return redirect('pricing:detalle',pk=pk)
                    obj.cantidad = Decimal('1')
                    obj.tarifa_unitaria = valor
                    obj.tarifa_origen_nombre = f'{politica.nombre} · {politica.get_metodo_display()}'
                    if not obj.descripcion:
                        obj.descripcion = politica.get_metodo_display()
            elif obj.tipo == OperationalCost.Tipo.CIF and obj.aplica:
                cif = CifConfig.objects.filter(activo=True).order_by('-actualizado_en').first()
                if not cif or cif.tarifa_hora <= 0:
                    messages.error(request,'Configure primero la matriz CIF y su base de horas productivas.')
                    return redirect('pricing:detalle',pk=pk)
                horas_mod = sum((Decimal(c.cantidad or 0) for c in calc.costos_operativos.filter(tipo=OperationalCost.Tipo.MANO_OBRA, aplica=True)), Decimal('0'))
                if horas_mod <= 0:
                    messages.error(request,'Para aplicar CIF por hora productiva, cargue primero las horas de MOD directa del trabajo.')
                    return redirect('pricing:detalle',pk=pk)
                obj.cantidad = horas_mod
                obj.tarifa_unitaria = cif.tarifa_hora
                obj.tarifa_origen_nombre = f'{cif.nombre} · tarifa vigente'
                if not obj.descripcion:
                    obj.descripcion = f'CIF aplicado sobre {horas_mod} h-h de MOD directa'
            if obj.tipo == OperationalCost.Tipo.FLETE and obj.concepto not in {'PERSONAL','EQUIPO','COMBUSTIBLE','TIQUETES','OTRO'}:
                messages.error(request,'Seleccione un concepto válido para Transporte / Movilización.')
                return redirect('pricing:detalle',pk=pk)
            if obj.tipo == OperationalCost.Tipo.VIATICOS and obj.concepto not in {'ALOJAMIENTO','ALIMENTACION','OTRO'}:
                messages.error(request,'Seleccione Alojamiento, Alimentación u Otro para Viáticos.')
                return redirect('pricing:detalle',pk=pk)
            if obj.tipo not in {OperationalCost.Tipo.FLETE, OperationalCost.Tipo.VIATICOS}:
                obj.concepto = ''
            if obj.aplica and obj.tarifa_unitaria <= 0:
                messages.error(request,'Si el costo operativo aplica, la tarifa/valor debe ser mayor que $0.')
            else:
                obj.save(); messages.success(request,f'Costo operativo revisado: {obj.get_tipo_display()}.')
        else:
            messages.error(request,'Revise los datos del costo operativo.')
    return redirect('pricing:detalle',pk=pk)

@costos_required
def eliminar_costo_operativo(request,pk,cost_id):
    calc=get_object_or_404(PriceCalculation,pk=pk)
    if request.method=='POST' and calc.estado==PriceCalculation.Estado.BORRADOR:
        get_object_or_404(calc.costos_operativos,pk=cost_id).delete(); messages.success(request,'Costo operativo eliminado.')
    return redirect('pricing:detalle',pk=pk)

@costos_required
def actualizar_cabecera(request,pk):
    calc=get_object_or_404(PriceCalculation,pk=pk)
    if request.method=='POST' and calc.estado==PriceCalculation.Estado.BORRADOR:
        try:
            gm=Decimal((request.POST.get('gm') or '0').replace(',','.'))/100
            trm=Decimal((request.POST.get('trm') or '0').replace(',','.'))
            if gm<0 or gm>=1 or trm<=0: raise ValueError
            calc.gm=gm; calc.trm=trm; calc.save()
            calc.precio_comercial=calc.precio_calculado; calc.save(update_fields=['precio_comercial','actualizado_en'])
            messages.success(request,'Cálculo actualizado. El precio maestro aún NO ha cambiado.')
        except Exception: messages.error(request,'GM o TRM inválido.')
    return redirect('pricing:detalle',pk=pk)

@costos_required
@transaction.atomic
def publicar(request,pk):
    calc=get_object_or_404(PriceCalculation.objects.select_for_update().select_related('item_venta'),pk=pk)
    if request.method!='POST': return redirect('pricing:detalle',pk=pk)
    if calc.estado==PriceCalculation.Estado.PUBLICADO:
        messages.info(request,'Este cálculo ya fue publicado.'); return redirect('pricing:detalle',pk=pk)
    if not calc.lineas.exists():
        messages.error(request,'No puede publicar un precio sin costos cargados.'); return redirect('pricing:detalle',pk=pk)
    pendientes = calc.lineas.filter(costo_unitario__lte=0, costo_cero_justificado=False)
    if pendientes.exists():
        codigos = ', '.join((x.codigo or x.descripcion) for x in pendientes[:5])
        messages.error(request,f'No se puede publicar: hay costos en $0 sin justificar ({codigos}). Registre el costo o marque Sin costo / incluido con motivo.')
        return redirect('pricing:detalle',pk=pk)
    calc.precio_comercial = calc.precio_calculado
    if calc.precio_comercial<=0:
        messages.error(request,'El precio calculado debe ser mayor que cero.'); return redirect('pricing:detalle',pk=pk)
    item=calc.item_venta.__class__.objects.select_for_update().get(pk=calc.item_venta_id)
    calc.precio_anterior=item.precio_venta
    item.precio_venta=calc.precio_comercial
    item.precio_actualizado_en=timezone.now()
    item.precio_actualizado_por=request.user
    item.save(update_fields=['precio_venta','precio_actualizado_en','precio_actualizado_por','updated_at'])
    calc.estado=PriceCalculation.Estado.PUBLICADO; calc.publicado_por=request.user; calc.publicado_en=timezone.now(); calc.save()
    messages.success(request,f'Precio publicado: {item.codigo} = ${calc.precio_comercial:,.0f}. Inventario IMPETUS quedó actualizado.')
    return redirect('pricing:detalle',pk=pk)


@costos_required
def tarifas_mod(request):
    tarifas=LaborRate.objects.all().order_by('nombre')
    form=LaborRateForm()
    return render(request,'pricing/tarifas_mod.html',{'tarifas':tarifas,'form':form})

@costos_required
@transaction.atomic
def guardar_tarifa_mod(request, rate_id=None):
    rate=get_object_or_404(LaborRate,pk=rate_id) if rate_id else None
    if request.method!='POST':
        return redirect('pricing:tarifas_mod')
    form=LaborRateForm(request.POST, instance=rate)
    if form.is_valid():
        obj=form.save(commit=False); obj.actualizado_por=request.user; obj.save()
        LaborRateHistory.objects.create(tarifa=obj, costo_empresa_mes=obj.costo_empresa_mes, participacion_pct=obj.participacion_pct, horas_productivas_mes=obj.horas_productivas_mes, costo_hora=obj.costo_hora, registrado_por=request.user)
        messages.success(request,f'Tarifa actualizada: {obj.nombre} = ${obj.costo_hora:,.0f}/h.')
    else:
        messages.error(request,'Revise los datos de la tarifa.')
    return redirect('pricing:tarifas_mod')


@costos_required
def tarifa_banco(request):
    banco=BankTestRate.objects.filter(activo=True).order_by('-actualizado_en').first() or BankTestRate()
    return render(request,'pricing/tarifa_banco.html',{'banco':banco,'form':BankTestRateForm(instance=banco if banco.pk else None)})

@costos_required
@transaction.atomic
def guardar_tarifa_banco(request):
    banco=BankTestRate.objects.filter(activo=True).order_by('-actualizado_en').first()
    if request.method!='POST': return redirect('pricing:tarifa_banco')
    form=BankTestRateForm(request.POST,instance=banco)
    if form.is_valid():
        obj=form.save(commit=False); obj.actualizado_por=request.user; obj.save()
        campos=['nombre','valor_banco_equipos','valor_residual','vida_util_anios','horas_uso_mes','potencia_promedio_kw','tarifa_energia_kwh','mantenimiento_anual','calibracion_anual','otros_costos_anuales','contingencia_pct','activo']
        BankTestRateHistory.objects.create(tarifa=obj,datos={k:str(getattr(obj,k)) for k in campos},costo_hora=obj.costo_hora,configuracion_completa=obj.configuracion_completa,registrado_por=request.user)
        estado='COMPLETA' if obj.configuracion_completa else 'PROVISIONAL'
        messages.success(request,f'Tarifa de banco guardada: ${obj.costo_hora:,.0f}/h · {estado}.')
    else: messages.error(request,'Revise los datos de la configuración del banco.')
    return redirect('pricing:tarifa_banco')


@costos_required
def configuracion_consumibles(request):
    politica = ConsumablesPolicy.objects.filter(activo=True).order_by('-actualizado_en').first() or ConsumablesPolicy()
    return render(request,'pricing/consumibles_config.html',{'politica':politica,'form':ConsumablesPolicyForm(instance=politica if politica.pk else None)})

@costos_required
@transaction.atomic
def guardar_configuracion_consumibles(request):
    politica = ConsumablesPolicy.objects.filter(activo=True).order_by('-actualizado_en').first()
    if request.method != 'POST':
        return redirect('pricing:configuracion_consumibles')
    form = ConsumablesPolicyForm(request.POST, instance=politica)
    if form.is_valid():
        obj=form.save(commit=False); obj.actualizado_por=request.user; obj.save()
        ConsumablesPolicyHistory.objects.create(politica=obj, metodo=obj.metodo, valor_fijo=obj.valor_fijo, porcentaje_mod=obj.porcentaje_mod, registrado_por=request.user)
        messages.success(request,f'Política de consumibles guardada: {obj.get_metodo_display()}.')
    else:
        messages.error(request,'Revise los datos de la política de consumibles.')
    return redirect('pricing:configuracion_consumibles')


@costos_required
def configuracion_cif(request):
    config = CifConfig.objects.filter(activo=True).order_by('-actualizado_en').first()
    if not config:
        config = CifConfig.objects.create(actualizado_por=request.user)
    conceptos = config.conceptos.all().order_by('categoria','concepto')
    recursos_mod = LaborRate.objects.filter(activo=True).order_by('nombre')
    return render(request,'pricing/cif_config.html',{'config':config,'conceptos':conceptos,'config_form':CifConfigForm(instance=config),'item_form':CifItemForm(),'recursos_mod':recursos_mod})

@costos_required
@transaction.atomic
def guardar_configuracion_cif(request):
    config = CifConfig.objects.filter(activo=True).order_by('-actualizado_en').first()
    if request.method != 'POST': return redirect('pricing:configuracion_cif')
    form=CifConfigForm(request.POST,instance=config)
    if form.is_valid():
        obj=form.save(commit=False); obj.actualizado_por=request.user; obj.save()
        CifConfigHistory.objects.create(configuracion=obj,datos={'nombre':obj.nombre,'modo_base_horas':obj.modo_base_horas,'horas_productivas_base_mes':str(obj.horas_productivas_base_mes),'horas_productivas_efectivas_mes':str(obj.horas_productivas_efectivas_mes),'conceptos':[{'concepto':x.concepto,'categoria':x.categoria,'costo_mes':str(x.costo_mes),'participacion_pct':str(x.participacion_pct),'costo_imputable_mes':str(x.costo_imputable_mes)} for x in obj.conceptos.filter(activo=True)]},costo_indirecto_mes=obj.costo_indirecto_mes,tarifa_hora=obj.tarifa_hora,registrado_por=request.user)
        messages.success(request,f'Matriz CIF guardada. Tarifa actual: ${obj.tarifa_hora:,.0f}/h-h.')
    else: messages.error(request,'Revise la configuración CIF.')
    return redirect('pricing:configuracion_cif')

@costos_required
@transaction.atomic
def agregar_cif_item(request):
    config = CifConfig.objects.filter(activo=True).order_by('-actualizado_en').first()
    if not config:
        config=CifConfig.objects.create(actualizado_por=request.user)
    if request.method=='POST':
        form=CifItemForm(request.POST)
        if form.is_valid():
            obj=form.save(commit=False); obj.configuracion=config; obj.save()
            messages.success(request,f'Concepto CIF agregado: {obj.concepto}.')
        else: messages.error(request,'Revise el concepto CIF.')
    return redirect('pricing:configuracion_cif')

@costos_required
@transaction.atomic
def eliminar_cif_item(request,item_id):
    if request.method=='POST':
        item=get_object_or_404(CifItem,pk=item_id); item.delete(); messages.success(request,'Concepto CIF eliminado.')
    return redirect('pricing:configuracion_cif')
