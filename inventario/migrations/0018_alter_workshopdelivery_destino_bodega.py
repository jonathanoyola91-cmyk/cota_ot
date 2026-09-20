from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0017_inventoryreservation_cantidad_consumida"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workshopdelivery",
            name="destino",
            field=models.CharField(
                choices=[
                    ("TALLER", "Taller"),
                    ("CAMPO", "Campo"),
                    ("INVENTARIO", "Inventario / bodega"),
                ],
                default="TALLER",
                max_length=20,
            ),
        ),
    ]
