from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("taller", "0010_posicion_y_puntos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name="instrumentometrologico", name="marca", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="instrumentometrologico", name="modelo", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="instrumentometrologico", name="serial", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="instrumentometrologico", name="unidad", field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="instrumentometrologico", name="ubicacion", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="instrumentometrologico", name="responsable", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="instrumentometrologico", name="estado", field=models.CharField(choices=[("ACTIVO", "Activo"), ("FUERA_SERVICIO", "Fuera de servicio"), ("BAJA", "Dado de baja")], default="ACTIVO", max_length=20)),
        migrations.AddField(model_name="instrumentometrologico", name="laboratorio", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="instrumentometrologico", name="numero_certificado", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="instrumentometrologico", name="certificado", field=models.FileField(blank=True, null=True, upload_to="taller/metrologia/certificados/%Y/%m/")),
        migrations.AddField(model_name="instrumentometrologico", name="observaciones", field=models.TextField(blank=True)),
        migrations.AlterField(model_name="instrumentometrologico", name="nombre", field=models.CharField(help_text="Tipo de instrumento: Micrómetro, Comparador, Calibrador, etc.", max_length=120)),
        migrations.CreateModel(
            name="CalibracionInstrumento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_calibracion", models.DateField()),
                ("fecha_vencimiento", models.DateField()),
                ("laboratorio", models.CharField(blank=True, max_length=150)),
                ("numero_certificado", models.CharField(blank=True, max_length=100)),
                ("certificado", models.FileField(blank=True, null=True, upload_to="taller/metrologia/certificados/%Y/%m/")),
                ("observaciones", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("instrumento", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="historial_calibraciones", to="taller.instrumentometrologico")),
                ("registrado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="calibraciones_metrologia_registradas", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-fecha_calibracion", "-id"]},
        ),
    ]
