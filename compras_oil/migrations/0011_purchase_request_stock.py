from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compras_oil", "0010_purchaserequest_revision_reservas_pendiente")]

    operations = [
        migrations.AlterField(
            model_name="purchaserequest",
            name="bom",
            field=models.OneToOneField(blank=True, null=True, on_delete=models.PROTECT, related_name="compra", to="bom.bom"),
        ),
        migrations.AddField(
            model_name="purchaserequest",
            name="origen",
            field=models.CharField(choices=[("PAW", "PAW / servicio"), ("STOCK", "Reposición de stock / bodega")], default="PAW", max_length=12),
        ),
        migrations.AddField(
            model_name="purchaserequest",
            name="empresa_destino",
            field=models.CharField(choices=[("IMPETUS", "IMPETUS HPS"), ("OIL_GAS", "OIL & GAS SUPPORT")], default="IMPETUS", max_length=12),
        ),
        migrations.AddField(
            model_name="purchaserequest",
            name="motivo_stock",
            field=models.TextField(blank=True, default=""),
        ),
    ]
