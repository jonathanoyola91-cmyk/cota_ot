from decimal import Decimal
from django.db import migrations, models


def inicializar_revisado(apps, schema_editor):
    PurchaseLine = apps.get_model("compras_oil", "PurchaseLine")
    # Todo lo perteneciente a solicitudes que YA habían sido confirmadas por
    # Inventario antes de este cambio se considera procesado. Así, al desplegar
    # la migración no reaparecen líneas históricas ni se duplican reservas/compras.
    qs = PurchaseLine.objects.filter(request__inventario_revisado_en__isnull=False)
    for linea in qs.iterator():
        linea.cantidad_revisada_inventario = linea.cantidad_requerida or Decimal("0")
        linea.save(update_fields=["cantidad_revisada_inventario"])


def revertir(apps, schema_editor):
    PurchaseLine = apps.get_model("compras_oil", "PurchaseLine")
    PurchaseLine.objects.update(cantidad_revisada_inventario=Decimal("0"))


class Migration(migrations.Migration):
    dependencies = [
        ("compras_oil", "0008_purchaserequest_revision_inventario"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseline",
            name="cantidad_revisada_inventario",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=12),
        ),
        migrations.RunPython(inicializar_revisado, revertir),
    ]
