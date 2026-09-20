from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0018_alter_workshopdelivery_destino_bodega"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workshopdelivery",
            name="destino",
            field=models.CharField(
                choices=[
                    ("TALLER", "Taller"),
                    ("CAMPO", "Campo"),
                    ("CLIENTE", "Cliente / despacho"),
                    ("INVENTARIO", "Inventario / bodega"),
                ],
                default="TALLER",
                max_length=20,
            ),
        ),
    ]
