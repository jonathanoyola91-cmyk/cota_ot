from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('pricing', '0002_linea_costo_cero_justificado')]
    operations = [
        migrations.CreateModel(
            name='OperationalCost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('MANO_OBRA','Mano de obra'),('BANCO','Banco de prueba / QA-QC'),('CONSUMIBLES','Consumibles generales'),('FLETE','Flete / transporte')], max_length=20)),
                ('aplica', models.BooleanField(default=True)),
                ('revisado', models.BooleanField(default=True)),
                ('descripcion', models.CharField(blank=True, default='', max_length=220)),
                ('cantidad', models.DecimalField(decimal_places=3, default=1, help_text='Horas para mano de obra/banco; unidades para otros costos.', max_digits=12)),
                ('tarifa_unitaria', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('observacion', models.CharField(blank=True, default='', max_length=220)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('calculo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='costos_operativos', to='pricing.pricecalculation')),
            ],
            options={'ordering':['tipo','id']},
        )
    ]
