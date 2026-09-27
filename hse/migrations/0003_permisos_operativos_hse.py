from django.db import migrations


def asignar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    mapa = {
        'GERENCIA': ['gestionar_dotacion'],
        'INVENTARIO': ['entregar_dotacion', 'gestionar_stock_hse'],
        'ADMIN': ['gestionar_dotacion', 'entregar_dotacion', 'gestionar_stock_hse'],
    }
    for grupo_nombre, codenames in mapa.items():
        grupo = Group.objects.filter(name__iexact=grupo_nombre).first()
        if not grupo:
            continue
        for codename in codenames:
            permiso = Permission.objects.filter(codename=codename, content_type__app_label='hse').first()
            if permiso:
                grupo.permissions.add(permiso)

class Migration(migrations.Migration):
    dependencies = [('hse', '0002_hserequest_motivo_entrega')]
    operations = [
        migrations.AlterModelOptions(
            name='hsestock',
            options={'ordering':['codigo'], 'permissions':[('gestionar_dotacion','Puede gestionar dotación'),('entregar_dotacion','Puede entregar EPP y dotación'),('gestionar_stock_hse','Puede gestionar bodega y stock HSE')]},
        ),
        migrations.RunPython(asignar_permisos, migrations.RunPython.noop),
    ]
