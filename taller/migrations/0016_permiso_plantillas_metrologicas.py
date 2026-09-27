from django.db import migrations


def asignar_permiso(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    try:
        permiso = Permission.objects.get(codename='gestionar_plantillas_metrologicas', content_type__app_label='taller')
    except Permission.DoesNotExist:
        return
    for nombre in ('ADMIN',):
        grupo = Group.objects.filter(name__iexact=nombre).first()
        if grupo:
            grupo.permissions.add(permiso)

class Migration(migrations.Migration):
    dependencies = [('taller', '0015_serial_equipo_camara')]
    operations = [
        migrations.AlterModelOptions(
            name='plantillaeje',
            options={'ordering':['nombre'], 'verbose_name':'Plantilla metrológica de eje', 'verbose_name_plural':'Plantillas metrológicas de ejes', 'permissions':[('gestionar_plantillas_metrologicas','Puede crear y editar plantillas metrológicas')]},
        ),
        migrations.RunPython(asignar_permiso, migrations.RunPython.noop),
    ]
