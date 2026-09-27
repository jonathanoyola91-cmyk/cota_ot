from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("taller", "0011_control_calibracion_instrumentos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="inspeccioneje", name="inspeccion_origen",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reinspecciones", to="taller.inspeccioneje"),
        ),
        migrations.AddField(
            model_name="inspeccioneje", name="numero_inspeccion",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.CreateModel(
            name="OrdenMecanizadoEje",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trabajo_requerido", models.TextField()),
                ("medida_objetivo", models.CharField(blank=True, max_length=250)),
                ("estado", models.CharField(choices=[("PENDIENTE","Pendiente"),("EN_PROCESO","En proceso"),("TERMINADO","Terminado / listo para reinspección"),("REINSPECCIONADO","Reinspeccionado")], default="PENDIENTE", max_length=20)),
                ("observaciones_taller", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("terminado_en", models.DateTimeField(blank=True, null=True)),
                ("creado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mecanizados_eje_creados", to=settings.AUTH_USER_MODEL)),
                ("responsable", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mecanizados_eje_asignados", to=settings.AUTH_USER_MODEL)),
                ("inspeccion_origen", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="orden_mecanizado", to="taller.inspeccioneje")),
            ],
            options={"ordering":["-creado_en"]},
        ),
    ]
