from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("taller", "0014_reparacion_fabricacion_tipos_reutilizacion")]
    operations = [
        migrations.AddField(model_name="inspeccioneje", name="serial_equipo", field=models.CharField(blank=True, max_length=100, verbose_name="Serial equipo / cámara")),
        migrations.AlterField(model_name="inspeccioneje", name="serial_eje", field=models.CharField(blank=True, max_length=100, verbose_name="Serial de la pieza")),
    ]
