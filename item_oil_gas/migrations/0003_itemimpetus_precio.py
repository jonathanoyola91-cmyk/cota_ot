from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('item_oil_gas','0002_itemimpetus'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='itemimpetus',name='precio_venta',field=models.DecimalField(decimal_places=2,default=0,max_digits=18,verbose_name='Precio de venta')),
        migrations.AddField(model_name='itemimpetus',name='precio_actualizado_en',field=models.DateTimeField(blank=True,null=True)),
        migrations.AddField(model_name='itemimpetus',name='precio_actualizado_por',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='precios_item_impetus_actualizados',to=settings.AUTH_USER_MODEL)),
    ]
