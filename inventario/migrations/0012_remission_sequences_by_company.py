from django.db import migrations, models


def preparar_secuencias(apps, schema_editor):
    RemissionSequence = apps.get_model("inventario", "RemissionSequence")
    DispatchRemission = apps.get_model("inventario", "DispatchRemission")

    # La tabla anterior manejaba un único contador. Se reemplaza por dos series.
    RemissionSequence.objects.all().delete()

    max_impetus = (
        DispatchRemission.objects.filter(empresa="IMPETUS")
        .aggregate(models.Max("consecutivo"))["consecutivo__max"]
    )
    max_oil = (
        DispatchRemission.objects.filter(empresa="OIL_GAS")
        .aggregate(models.Max("consecutivo"))["consecutivo__max"]
    )

    # Respetar como mínimo los últimos documentos históricos indicados.
    RemissionSequence.objects.create(
        empresa="IMPETUS",
        ultimo=max(69, max_impetus or 0),
    )
    RemissionSequence.objects.create(
        empresa="OIL_GAS",
        ultimo=max(1511, max_oil or 0),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0011_dispatchremission_empresa_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="remissionsequence",
            name="empresa",
            field=models.CharField(default="OIL_GAS", max_length=12),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="remissionsequence",
            name="ultimo",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="dispatchremission",
            name="consecutivo",
            field=models.PositiveIntegerField(),
        ),
        migrations.RunPython(preparar_secuencias, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="remissionsequence",
            name="empresa",
            field=models.CharField(max_length=12, unique=True),
        ),
        migrations.AddConstraint(
            model_name="dispatchremission",
            constraint=models.UniqueConstraint(
                fields=("empresa", "consecutivo"),
                name="uniq_remision_empresa_consecutivo",
            ),
        ),
    ]
