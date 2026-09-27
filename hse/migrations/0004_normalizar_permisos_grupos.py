from django.db import migrations


def asignar_permisos_case_insensitive(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    mapa = {
        'gerencia': ['gestionar_dotacion'],
        'inventario': ['entregar_dotacion', 'gestionar_stock_hse'],
        'admin': ['gestionar_dotacion', 'entregar_dotacion', 'gestionar_stock_hse'],
        'administracion': ['gestionar_dotacion', 'entregar_dotacion', 'gestionar_stock_hse'],
    }

    for nombre, codenames in mapa.items():
        # __iexact hace que GERENCIA, gerencia, Gerencia, etc. sean equivalentes.
        for grupo in Group.objects.filter(name__iexact=nombre):
            permisos = Permission.objects.filter(
                content_type__app_label='hse',
                codename__in=codenames,
            )
            grupo.permissions.add(*permisos)


class Migration(migrations.Migration):
    dependencies = [('hse', '0003_permisos_operativos_hse')]
    operations = [
        migrations.RunPython(asignar_permisos_case_insensitive, migrations.RunPython.noop),
    ]
