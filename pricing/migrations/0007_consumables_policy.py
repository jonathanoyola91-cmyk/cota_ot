from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [('pricing','0006_operationalcost_transport_viatics'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='ConsumablesPolicy', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('nombre',models.CharField(default='Consumibles generales',max_length=140)),
            ('metodo',models.CharField(choices=[('FIJO','Valor fijo por trabajo'),('PCT_MOD','Porcentaje sobre MOD directa'),('MANUAL','Manual por trabajo')],default='MANUAL',max_length=12)),
            ('valor_fijo',models.DecimalField(decimal_places=2,default=0,max_digits=18)),
            ('porcentaje_mod',models.DecimalField(decimal_places=3,default=0,help_text='Porcentaje sobre el total de MOD directa.',max_digits=7)),
            ('activo',models.BooleanField(default=True)),('actualizado_en',models.DateTimeField(auto_now=True)),
            ('actualizado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='politicas_consumibles_actualizadas',to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='ConsumablesPolicyHistory', fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('metodo',models.CharField(max_length=12)),('valor_fijo',models.DecimalField(decimal_places=2,default=0,max_digits=18)),
            ('porcentaje_mod',models.DecimalField(decimal_places=3,default=0,max_digits=7)),('vigente_desde',models.DateTimeField(default=django.utils.timezone.now)),
            ('politica',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='historial',to='pricing.consumablespolicy')),
            ('registrado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
        ],options={'ordering':['-vigente_desde']}),
    ]
