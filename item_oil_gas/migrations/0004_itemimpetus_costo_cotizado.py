from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('item_oil_gas', '0003_itemimpetus_precio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado', field=models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name='Costo cotizado')),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_moneda', field=models.CharField(choices=[('COP','COP'),('USD','USD')], default='COP', max_length=3)),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_proveedor', field=models.CharField(blank=True, default='', max_length=160)),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_fecha', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_vigente_hasta', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_referencia', field=models.CharField(blank=True, default='', max_length=120)),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_observacion', field=models.CharField(blank=True, default='', max_length=300)),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_actualizado_en', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='itemimpetus', name='costo_cotizado_por', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='costos_cotizados_item_impetus', to=settings.AUTH_USER_MODEL)),
    ]
