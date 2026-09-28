from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("campo", "0009_fieldservicebonusclaim")]
    operations = [
        migrations.AddField(model_name="fieldservicebonusclaim", name="alojamiento", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
        migrations.AddField(model_name="fieldservicebonusclaim", name="alimentacion", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
        migrations.AddField(model_name="fieldservicebonusclaim", name="lavanderia", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
        migrations.AddField(model_name="fieldservicebonusclaim", name="transporte_personal", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
        migrations.AddField(model_name="fieldservicebonusclaim", name="vuelo_ida_aplica", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="fieldservicebonusclaim", name="vuelo_ida_valor", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
        migrations.AddField(model_name="fieldservicebonusclaim", name="vuelo_regreso_aplica", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="fieldservicebonusclaim", name="vuelo_regreso_valor", field=models.DecimalField(decimal_places=2, default=0, max_digits=14)),
    ]
