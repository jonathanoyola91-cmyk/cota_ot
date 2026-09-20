from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("inventario", "0015_alter_workshopdelivery_destino"), ("compras_oil", "0008_purchaserequest_revision_inventario")]

    operations = [
        migrations.AddField(
            model_name="inventoryreservation",
            name="purchase_line",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reservas_inventario", to="compras_oil.purchaseline"),
        ),
        migrations.AddField(
            model_name="inventoryreservation",
            name="es_transicion",
            field=models.BooleanField(default=False, help_text="Reserva creada para PAW ya activo al momento de iniciar el control de existencias."),
        ),
    ]
