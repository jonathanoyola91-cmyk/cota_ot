from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies=[('pricing','0004_labor_rates'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
      migrations.CreateModel(name='BankTestRate',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('nombre',models.CharField(default='Banco de prueba / QA-QC',max_length=140)),('valor_banco_equipos',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('valor_residual',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('vida_util_anios',models.DecimalField(decimal_places=2,default=10,max_digits=8)),('horas_uso_mes',models.DecimalField(decimal_places=2,default=0,max_digits=10)),('potencia_promedio_kw',models.DecimalField(decimal_places=2,default=0,max_digits=10)),('tarifa_energia_kwh',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('mantenimiento_anual',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('calibracion_anual',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('otros_costos_anuales',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('contingencia_pct',models.DecimalField(decimal_places=2,default=0,max_digits=6)),('activo',models.BooleanField(default=True)),('actualizado_en',models.DateTimeField(auto_now=True)),('actualizado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='tarifas_banco_actualizadas',to=settings.AUTH_USER_MODEL)),]),
      migrations.CreateModel(name='BankTestRateHistory',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('datos',models.JSONField(default=dict)),('costo_hora',models.DecimalField(decimal_places=2,default=0,max_digits=18)),('configuracion_completa',models.BooleanField(default=False)),('vigente_desde',models.DateTimeField(default=django.utils.timezone.now)),('registrado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),('tarifa',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='historial',to='pricing.banktestrate')),],options={'ordering':['-vigente_desde']}),
    ]
