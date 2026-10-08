from django.db import migrations, models


def clasificar_existentes(apps, schema_editor):
    Instrumento = apps.get_model("taller", "InstrumentoMetrologico")
    from django.utils import timezone
    hoy = timezone.localdate()
    for equipo in Instrumento.objects.all().iterator():
        if equipo.fecha_calibracion and equipo.fecha_vencimiento:
            condicion = "CALIBRADO" if equipo.fecha_vencimiento >= hoy else "DESCALIBRADO"
        else:
            condicion = "POR_VERIFICAR"
        Instrumento.objects.filter(pk=equipo.pk).update(condicion_calibracion=condicion)


class Migration(migrations.Migration):
    dependencies = [("taller", "0017_normalizar_permiso_metrologia_grupos")]
    operations = [
        migrations.AddField(model_name="instrumentometrologico", name="condicion_calibracion", field=models.CharField(choices=[("CALIBRADO", "Calibrado"), ("DESCALIBRADO", "Descalibrado / sin calibración vigente"), ("NO_REQUIERE", "No requiere calibración"), ("POR_VERIFICAR", "Pendiente de verificar")], default="POR_VERIFICAR", max_length=20)),
        migrations.RunPython(clasificar_existentes, migrations.RunPython.noop),
    ]
