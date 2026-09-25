from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pricing', '0005_bank_test_rate')]

    operations = [
        migrations.AddField(
            model_name='operationalcost',
            name='concepto',
            field=models.CharField(blank=True, choices=[
                ('PERSONAL', 'Movilización de personal'),
                ('EQUIPO', 'Transporte de equipo'),
                ('COMBUSTIBLE', 'Combustible / peajes'),
                ('TIQUETES', 'Tiquetes'),
                ('ALOJAMIENTO', 'Alojamiento'),
                ('ALIMENTACION', 'Alimentación'),
                ('OTRO', 'Otro'),
            ], default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='operationalcost',
            name='tipo',
            field=models.CharField(choices=[
                ('MANO_OBRA', 'Mano de obra'),
                ('BANCO', 'Banco de prueba / QA-QC'),
                ('CONSUMIBLES', 'Consumibles generales'),
                ('FLETE', 'Transporte / movilización'),
                ('VIATICOS', 'Viáticos'),
            ], max_length=20),
        ),
    ]
