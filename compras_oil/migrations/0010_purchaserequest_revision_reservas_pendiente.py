from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compras_oil", "0009_purchaseline_cantidad_revisada_inventario")]
    operations = [migrations.AddField(
        model_name="purchaserequest",
        name="revision_reservas_pendiente",
        field=models.BooleanField(default=False),
    )]
