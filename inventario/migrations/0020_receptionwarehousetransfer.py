from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventario", "0019_alter_workshopdelivery_destino_cliente"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReceptionWarehouseTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("empresa_destino", models.CharField(choices=[("IMPETUS", "IMPETUS HPS"), ("OIL_GAS", "OIL & GAS SUPPORT")], max_length=12)),
                ("cantidad", models.DecimalField(decimal_places=3, max_digits=14)),
                ("motivo", models.TextField()),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("creado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transferencias_paw_bodega_creadas", to=settings.AUTH_USER_MODEL)),
                ("reception_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transferencias_bodega", to="inventario.inventoryreceptionline")),
                ("stock_destino", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="devoluciones_paw_destino", to="inventario.inventorystock")),
                ("stock_origen", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="devoluciones_paw_origen", to="inventario.inventorystock")),
            ],
            options={"ordering": ["-creado_en", "-id"]},
        ),
        migrations.AlterField(
            model_name="inventorymovement",
            name="tipo",
            field=models.CharField(choices=[("INICIAL", "Inventario inicial"), ("AJUSTE_ENTRADA", "Ajuste positivo"), ("AJUSTE_SALIDA", "Ajuste negativo"), ("TRF_ENTRADA", "Transferencia entrada"), ("TRF_SALIDA", "Transferencia salida"), ("RECEPCION", "Recepción de compra"), ("ENTREGA", "Entrega / salida"), ("LIBERACION", "Liberación de reserva a bodega")], max_length=24),
        ),
    ]
