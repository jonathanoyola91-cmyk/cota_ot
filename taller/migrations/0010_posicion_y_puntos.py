from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("taller", "0009_mapa_real_ejes")]
    operations = [
        migrations.AddField(
            model_name="puntomedicioneje", name="posicion_y",
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Posición vertical del marcador sobre el plano (0-100%)", max_digits=5, null=True),
        ),
        migrations.RunSQL(
            "UPDATE taller_puntomedicioneje SET posicion_y = 50.00 WHERE posicion_y IS NULL",
            migrations.RunSQL.noop,
        ),
    ]
