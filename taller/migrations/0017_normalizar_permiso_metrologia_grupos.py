from django.db import migrations


def asignar_permiso_case_insensitive(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    permiso = Permission.objects.filter(
        codename='gestionar_plantillas_metrologicas',
        content_type__app_label='taller',
    ).first()
    if not permiso:
        return

    # Solo administración recibe configuración de plantillas automáticamente.
    # Taller/TALLER puede operar metrología, pero NO editar plantillas.
    for nombre in ('admin', 'administracion'):
        for grupo in Group.objects.filter(name__iexact=nombre):
            grupo.permissions.add(permiso)


class Migration(migrations.Migration):
    dependencies = [('taller', '0016_permiso_plantillas_metrologicas')]
    operations = [
        migrations.RunPython(asignar_permiso_case_insensitive, migrations.RunPython.noop),
    ]
