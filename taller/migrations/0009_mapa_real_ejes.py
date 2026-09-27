from decimal import Decimal
from django.db import migrations, models


def configurar_mapas(apps, schema_editor):
    Plantilla = apps.get_model('taller', 'PlantillaEje')
    Punto = apps.get_model('taller', 'PuntoMedicionEje')
    mapas = {
        'SHAFT K-35"-8S TRAILER PAD CENTRAL': ('k35.jpg', [5, 28, 52, 43, 49, 82, 95]),
        'SHAFT K-38"-8S ACR P-820-C': ('k38.jpg', [5, 28, 52, 43, 49, 82, 95]),
        'SHAFT K-27"-8S CHB-4 UND 2': ('k27.jpg', [8, 79, 52, 43, 49, 25]),
        'SHAFT TC1 NVT - HALF RING AND SLEEVE': ('tc1.jpg', [31, 18, 38, 63, 7]),
        'SHAFT 23T 1 XT - HALF RING AND SLEEVES': ('23t_half.jpg', [5, 25, 34, 55, 61, 68, 73, 94, 82, 86]),
        'SHAFT 23T 1 XT V2 - 34.54': ('23t_875.jpg', [5, 31, 39, 57, 74, 66, 8, 46, 58, 84]),
    }
    for nombre, (imagen, posiciones) in mapas.items():
        try:
            plantilla = Plantilla.objects.get(nombre=nombre)
        except Plantilla.DoesNotExist:
            continue
        plantilla.imagen_mapa = imagen
        plantilla.save(update_fields=['imagen_mapa'])
        for punto, x in zip(Punto.objects.filter(plantilla=plantilla).order_by('orden','id'), posiciones):
            punto.posicion_x = Decimal(str(x))
            punto.save(update_fields=['posicion_x'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('taller', '0008_puntos_ejes_23t')]
    operations = [
        migrations.AddField(
            model_name='plantillaeje', name='imagen_mapa',
            field=models.CharField(blank=True, help_text='Archivo de imagen técnica usado en el mapa de inspección', max_length=160),
        ),
        migrations.AddField(
            model_name='puntomedicioneje', name='posicion_x',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Posición horizontal del marcador sobre el plano (0-100%)', max_digits=5, null=True),
        ),
        migrations.RunPython(configurar_mapas, noop),
    ]
