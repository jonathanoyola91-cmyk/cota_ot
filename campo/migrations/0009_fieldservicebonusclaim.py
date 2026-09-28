from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [("campo", "0008_fieldservicepersonexpense_dia_trabajado_campo_and_more"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="FieldServiceBonusClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tecnico_nombre", models.CharField(max_length=150)),
                ("rol", models.CharField(choices=[("LIDER","Especialista líder"),("APOYO","Especialista apoyo")], max_length=10)),
                ("fecha", models.DateField(default=django.utils.timezone.localdate)),
                ("dia_trabajado_campo", models.BooleanField(default=True)),
                ("salida_despues_mediodia", models.BooleanField(default=False)),
                ("regreso_despues_6pm", models.BooleanField(default=False)),
                ("solo_viaje_traslado", models.BooleanField(default=False)),
                ("observaciones", models.CharField(blank=True, default="", max_length=250)),
                ("estado", models.CharField(choices=[("PENDIENTE","Pendiente de validación"),("APROBADO","Aprobado"),("RECHAZADO","Rechazado")], default="PENDIENTE", max_length=12)),
                ("validado_en", models.DateTimeField(blank=True, null=True)),
                ("observacion_validacion", models.CharField(blank=True, default="", max_length=250)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("servicio", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bonos_reportados", to="campo.fieldservice")),
                ("tecnico", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bonos_campo_reportados", to=settings.AUTH_USER_MODEL)),
                ("validado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bonos_campo_validados", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-fecha","-id"]}),
        migrations.AddConstraint(model_name="fieldservicebonusclaim", constraint=models.UniqueConstraint(fields=("servicio","tecnico","fecha"), name="uniq_bono_tecnico_servicio_fecha")),
    ]
