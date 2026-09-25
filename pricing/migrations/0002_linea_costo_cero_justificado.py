from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pricing', '0001_initial')]
    operations = [
        migrations.AddField(model_name='pricecalculationline', name='costo_cero_justificado', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='pricecalculationline', name='motivo_costo_cero', field=models.CharField(blank=True, default='', max_length=220)),
    ]
