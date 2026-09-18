from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("inventario", "0013_dispatchremission_anulacion"), ("compras_oil", "0007_alter_purchaseline_porcentaje_pago_and_more"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="InventoryStock", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("empresa", models.CharField(choices=[("IMPETUS","IMPETUS HPS"),("OIL_GAS","OIL & GAS SUPPORT")], max_length=12)),
            ("catalogo", models.CharField(max_length=20)), ("catalogo_item_id", models.PositiveIntegerField()),
            ("codigo", models.CharField(db_index=True,max_length=80)), ("descripcion",models.CharField(blank=True,default="",max_length=300)), ("unidad",models.CharField(blank=True,default="UND",max_length=30)),
            ("cantidad_fisica",models.DecimalField(decimal_places=3,default=0,max_digits=14)), ("cantidad_reservada",models.DecimalField(decimal_places=3,default=0,max_digits=14)), ("costo_promedio",models.DecimalField(decimal_places=4,default=0,max_digits=18)), ("actualizado_en",models.DateTimeField(auto_now=True)),
        ], options={"ordering":["empresa","codigo"]}),
        migrations.AddConstraint(model_name="inventorystock", constraint=models.UniqueConstraint(fields=("empresa","catalogo","catalogo_item_id"),name="uniq_stock_empresa_catalogo_item")),
        migrations.CreateModel(name="InventoryMovement", fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("tipo",models.CharField(choices=[("INICIAL","Inventario inicial"),("AJUSTE_ENTRADA","Ajuste positivo"),("AJUSTE_SALIDA","Ajuste negativo"),("TRF_ENTRADA","Transferencia entrada"),("TRF_SALIDA","Transferencia salida"),("RECEPCION","Recepción de compra"),("ENTREGA","Entrega / salida")],max_length=24)),
            ("cantidad",models.DecimalField(decimal_places=3,max_digits=14)), ("costo_unitario",models.DecimalField(decimal_places=4,default=0,max_digits=18)), ("saldo_anterior",models.DecimalField(decimal_places=3,default=0,max_digits=14)), ("saldo_nuevo",models.DecimalField(decimal_places=3,default=0,max_digits=14)), ("costo_promedio_anterior",models.DecimalField(decimal_places=4,default=0,max_digits=18)), ("costo_promedio_nuevo",models.DecimalField(decimal_places=4,default=0,max_digits=18)), ("referencia",models.CharField(blank=True,default="",max_length=80)), ("motivo",models.TextField(blank=True,default="")), ("creado_en",models.DateTimeField(auto_now_add=True)),
            ("creado_por",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="movimientos_stock_creados",to=settings.AUTH_USER_MODEL)), ("stock",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="movimientos",to="inventario.inventorystock")),
        ], options={"ordering":["-creado_en","-id"]}),
        migrations.CreateModel(name="InventoryReservation", fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("cantidad",models.DecimalField(decimal_places=3,max_digits=14)), ("estado",models.CharField(choices=[("ACTIVA","Activa"),("CONSUMIDA","Consumida/entregada"),("LIBERADA","Liberada")],default="ACTIVA",max_length=12)), ("creado_en",models.DateTimeField(auto_now_add=True)), ("cerrado_en",models.DateTimeField(blank=True,null=True)), ("observacion",models.TextField(blank=True,default="")),
            ("creado_por",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="reservas_inventario_creadas",to=settings.AUTH_USER_MODEL)), ("purchase_request",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="reservas_inventario",to="compras_oil.purchaserequest")), ("stock",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="reservas",to="inventario.inventorystock")),
        ]),
        migrations.CreateModel(name="InventoryTransfer", fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("empresa_origen",models.CharField(choices=[("IMPETUS","IMPETUS HPS"),("OIL_GAS","OIL & GAS SUPPORT")],max_length=12)), ("empresa_destino",models.CharField(choices=[("IMPETUS","IMPETUS HPS"),("OIL_GAS","OIL & GAS SUPPORT")],max_length=12)), ("cantidad",models.DecimalField(decimal_places=3,max_digits=14)), ("costo_unitario",models.DecimalField(decimal_places=4,default=0,max_digits=18)), ("motivo",models.TextField(blank=True,default="")), ("documento",models.CharField(blank=True,default="",max_length=100)), ("estado",models.CharField(choices=[("COMPLETADA","Completada"),("ANULADA","Anulada")],default="COMPLETADA",max_length=12)), ("creado_en",models.DateTimeField(auto_now_add=True)),
            ("creado_por",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="transferencias_inventario_creadas",to=settings.AUTH_USER_MODEL)), ("stock_destino",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="transferencias_entrada",to="inventario.inventorystock")), ("stock_origen",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="transferencias_salida",to="inventario.inventorystock")),
        ]),
    ]
