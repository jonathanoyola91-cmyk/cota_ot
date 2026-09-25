from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies=[('pricing','0003_operationalcost'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
      migrations.CreateModel(name='LaborRate',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('nombre',models.CharField(max_length=140,unique=True)),('costo_empresa_mes',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('participacion_pct',models.DecimalField(decimal_places=2,default=100,max_digits=6)),('horas_productivas_mes',models.DecimalField(decimal_places=2,default=176,max_digits=8)),('activo',models.BooleanField(default=True)),('actualizado_en',models.DateTimeField(auto_now=True)),('actualizado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='tarifas_mod_actualizadas',to=settings.AUTH_USER_MODEL))]),
      migrations.CreateModel(name='LaborRateHistory',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('costo_empresa_mes',models.DecimalField(decimal_places=2,max_digits=18)),('participacion_pct',models.DecimalField(decimal_places=2,max_digits=6)),('horas_productivas_mes',models.DecimalField(decimal_places=2,max_digits=8)),('costo_hora',models.DecimalField(decimal_places=2,max_digits=18)),('vigente_desde',models.DateTimeField(default=django.utils.timezone.now)),('registrado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),('tarifa',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='historial',to='pricing.laborrate'))],options={'ordering':['-vigente_desde']}),
      migrations.AddField(model_name='operationalcost',name='recurso_mod',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='costos_usados',to='pricing.laborrate')),
      migrations.AddField(model_name='operationalcost',name='tarifa_origen_nombre',field=models.CharField(blank=True,default='',max_length=140)),
    ]
