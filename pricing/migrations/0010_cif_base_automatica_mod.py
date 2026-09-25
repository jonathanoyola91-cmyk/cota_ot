from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pricing', '0009_create_costos_group')]
    operations = [
        migrations.AddField(
            model_name='cifconfig',
            name='modo_base_horas',
            field=models.CharField(choices=[('AUTOMATICA','Automática desde MOD activa'),('MANUAL','Manual / excepción')], default='AUTOMATICA', max_length=12),
        ),
        migrations.AlterField(
            model_name='cifconfig',
            name='horas_productivas_base_mes',
            field=models.DecimalField(decimal_places=2, default=176, help_text='Base manual. Solo se usa cuando el modo de distribución es Manual.', max_digits=10),
        ),
    ]
