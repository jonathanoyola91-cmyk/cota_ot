from django.conf import settings
from django.db import migrations, models


def copiar_apoyo_legacy(apps, schema_editor):
    FieldService = apps.get_model('campo', 'FieldService')
    for servicio in FieldService.objects.exclude(especialista_apoyo_usuario=None):
        servicio.especialistas_apoyo_usuarios.add(servicio.especialista_apoyo_usuario_id)


class Migration(migrations.Migration):
    dependencies = [
        ('campo', '0011_fieldservice_usuarios_tecnicos'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AlterField(
            model_name='fieldservice', name='especialista_apoyo_usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name='servicios_campo_como_apoyo_legacy', to=settings.AUTH_USER_MODEL, verbose_name='Especialista apoyo (legado)'),
        ),
        migrations.AddField(
            model_name='fieldservice', name='especialistas_apoyo_usuarios',
            field=models.ManyToManyField(blank=True, related_name='servicios_campo_como_apoyo', to=settings.AUTH_USER_MODEL, verbose_name='Especialistas de apoyo'),
        ),
        migrations.RunPython(copiar_apoyo_legacy, migrations.RunPython.noop),
        migrations.AddField(
            model_name='fieldservicebonusclaim', name='hidratacion',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
