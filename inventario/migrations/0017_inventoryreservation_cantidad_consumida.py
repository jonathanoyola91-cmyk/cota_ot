from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0016_inventoryreservation_purchase_line_transicion"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryreservation",
            name="cantidad_consumida",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
    ]
