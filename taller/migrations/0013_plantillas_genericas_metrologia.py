from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("taller", "0012_reinspeccion_mecanizado_ejes")]
    operations = [
        migrations.AddField(
            model_name="plantillaeje", name="tipo_pieza",
            field=models.CharField(choices=[("EJE", "Eje"), ("HOUSING", "Housing"), ("SLEEVE", "Sleeve / camisa"), ("CAMARA", "Cámara"), ("BOMBA", "Bomba"), ("OTRO", "Otra pieza")], default="EJE", max_length=20),
        ),
        migrations.AddField(
            model_name="plantillaeje", name="imagen_archivo",
            field=models.ImageField(blank=True, help_text="Plano o imagen técnica cargada para configurar los puntos", null=True, upload_to="taller/metrologia/plantillas/%Y/%m/"),
        ),
        migrations.AlterField(
            model_name="plantillaeje", name="imagen_mapa",
            field=models.CharField(blank=True, help_text="Imagen técnica histórica incluida con el sistema", max_length=160),
        ),
    ]
