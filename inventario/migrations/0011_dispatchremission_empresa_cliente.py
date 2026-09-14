from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0010_inventoryexit_dispatchremission"),
        ("quotes", "0004_cliente_quotation_cliente_registrado"),
    ]

    operations = [
        migrations.AddField(
            model_name="dispatchremission",
            name="empresa",
            field=models.CharField(
                choices=[("IMPETUS", "IMPETUS HPS"), ("OIL_GAS", "OIL & GAS SUPPORT")],
                default="IMPETUS",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="dispatchremission",
            name="cliente_registrado",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="remisiones_salida",
                to="quotes.cliente",
            ),
        ),
    ]
