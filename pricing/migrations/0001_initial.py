from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[('item_oil_gas','0003_itemimpetus_precio'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
      migrations.CreateModel(name='PriceCalculation',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('gm',models.DecimalField(decimal_places=4,default=Decimal('0.4000'),max_digits=6,verbose_name='Gross Margin')),
        ('trm',models.DecimalField(decimal_places=4,default=Decimal('1'),max_digits=14)),
        ('precio_comercial',models.DecimalField(decimal_places=2,default=0,help_text='Precio final que se publicará. Puede redondearse respecto al precio calculado.',max_digits=18)),
        ('estado',models.CharField(choices=[('BORRADOR','Borrador'),('PUBLICADO','Publicado')],default='BORRADOR',max_length=12)),
        ('observaciones',models.TextField(blank=True,default='')),('creado_en',models.DateTimeField(auto_now_add=True)),('actualizado_en',models.DateTimeField(auto_now=True)),('publicado_en',models.DateTimeField(blank=True,null=True)),('precio_anterior',models.DecimalField(blank=True,decimal_places=2,max_digits=18,null=True)),
        ('creado_por',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='calculos_precio_creados',to=settings.AUTH_USER_MODEL)),
        ('item_venta',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='calculos_precio',to='item_oil_gas.itemimpetus')),
        ('publicado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='precios_publicados',to=settings.AUTH_USER_MODEL)),
      ],options={'ordering':['-creado_en']}),
      migrations.CreateModel(name='PriceCalculationLine',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('codigo',models.CharField(blank=True,default='',max_length=80)),('descripcion',models.CharField(max_length=300)),('tipo',models.CharField(choices=[('INSUMO','Insumo / repuesto'),('SERVICIO','Servicio / costo directo'),('OTRO','Otro costo')],default='INSUMO',max_length=12)),('importacion',models.BooleanField(default=False)),('moneda',models.CharField(choices=[('COP','COP'),('USD','USD')],default='COP',max_length=3)),('cantidad',models.DecimalField(decimal_places=3,default=1,max_digits=12)),('costo_unitario',models.DecimalField(decimal_places=4,default=0,max_digits=18)),('fuente_costo',models.CharField(blank=True,default='Manual',max_length=120)),('iva_pct',models.DecimalField(decimal_places=4,default=Decimal('0.1900'),max_digits=6)),('iva_es_costo',models.BooleanField(default=False,help_text='Active solo cuando el IVA realmente constituye mayor costo.')),('alistamiento_pct',models.DecimalField(decimal_places=4,default=0,max_digits=6)),('administrativo_pct',models.DecimalField(decimal_places=4,default=0,max_digits=6)),('arancel_pct',models.DecimalField(decimal_places=4,default=0,max_digits=6)),
        ('calculo',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='lineas',to='pricing.pricecalculation')),('item',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='lineas_calculo_precio',to='item_oil_gas.itemimpetus')),
      ],options={'ordering':['id']})]
