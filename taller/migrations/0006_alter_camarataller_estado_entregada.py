from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("taller", "0005_camarataller_fecha_tear_down"),
    ]

    operations = [
        migrations.AlterField(
            model_name="camarataller",
            name="estado",
            field=models.CharField(
                choices=[
                    ("RECIBIDA", "Recibida"),
                    ("PENDIENTE_TD", "Pendiente Tear Down"),
                    ("TD_REALIZADO", "Tear Down realizado"),
                    ("PENDIENTE_COTIZACION", "Pendiente cotización"),
                    ("COTIZACION_ENVIADA", "Cotización enviada"),
                    ("PENDIENTE_APROBACION", "Pendiente aprobación"),
                    ("APROBADA", "Aprobada / Pendiente PAW"),
                    ("PAW_GENERADO", "PAW generado"),
                    ("ENTREGADA", "Entregada / Salió de Taller"),
                ],
                default="RECIBIDA",
                max_length=30,
            ),
        ),
    ]
