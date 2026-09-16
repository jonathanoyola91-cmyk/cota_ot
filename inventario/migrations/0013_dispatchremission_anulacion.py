from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0012_remission_sequences_by_company"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="dispatchremission",
            name="estado",
            field=models.CharField(
                choices=[("ACTIVA", "Activa"), ("ANULADA", "Anulada")],
                default="ACTIVA",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="dispatchremission",
            name="anulada_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="remisiones_salida_anuladas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="dispatchremission",
            name="anulada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dispatchremission",
            name="motivo_anulacion",
            field=models.TextField(blank=True),
        ),
    ]
