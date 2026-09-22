from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventario", "0021_deliverypendingcancellation")]

    operations = [
        migrations.AddField(
            model_name="inventoryexit",
            name="empresa",
            field=models.CharField(choices=[("IMPETUS", "IMPETUS HPS"), ("OIL_GAS", "OIL & GAS SUPPORT")], default="IMPETUS", max_length=12),
        ),
    ]
