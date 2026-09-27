from decimal import Decimal
from django.db import migrations


def cargar_puntos_23t(apps, schema_editor):
    Plantilla = apps.get_model('taller', 'PlantillaEje')
    Punto = apps.get_model('taller', 'PuntoMedicionEje')
    Inspeccion = apps.get_model('taller', 'InspeccionEje')
    Medicion = apps.get_model('taller', 'MedicionEje')

    datos = {
        'SHAFT 23T 1 XT - HALF RING AND SLEEVES': [
            ('A', 'Ø extremo / zona de acople', 'DIAMETRO', '38.0200', '37.9900', '38.0700', 'Micrómetro'),
            ('B', 'Ø ajuste D9', 'DIAMETRO', '25.4000', '25.4650', '25.5170', 'Micrómetro'),
            ('C', 'Ø ajuste f8', 'DIAMETRO', '40.9700', '40.9060', '40.9450', 'Micrómetro'),
            ('D', 'Ø asiento 60.0202', 'DIAMETRO', '60.0202', '60.0024', '60.0202', 'Micrómetro'),
            ('E', 'Ø asiento 60.02', 'DIAMETRO', '60.0200', '60.0000', '60.0200', 'Micrómetro'),
            ('F', 'Ø ajuste D11', 'DIAMETRO', '56.7200', '56.8200', '57.0100', 'Micrómetro'),
            ('G', 'Ø asiento', 'DIAMETRO', '59.9400', '59.8400', '59.9400', 'Micrómetro'),
            ('H', 'Ø extremo', 'DIAMETRO', '50.8000', '50.7500', '50.8000', 'Micrómetro'),
            ('I', 'Ø sección E-E', 'DIAMETRO', '41.5000', '41.4700', '41.5500', 'Micrómetro'),
            ('J', 'Ancho sección E-E', 'ANCHO', '15.8800', '15.8800', '15.9300', 'Micrómetro'),
        ],
        'SHAFT 23T 1 XT V2 - 34.54': [
            ('A', 'Ø extremo', 'DIAMETRO', '38.1000', '38.0240', '38.1000', 'Micrómetro'),
            ('B', 'Ø asiento 50.83', 'DIAMETRO', '50.8300', '50.8198', '50.8300', 'Micrómetro'),
            ('C', 'Ø asiento 57.20', 'DIAMETRO', '57.2000', '57.0980', '57.2000', 'Micrómetro'),
            ('D', 'Ø asiento 50.80', 'DIAMETRO', '50.8000', '50.7500', '50.8000', 'Micrómetro'),
            ('E', 'Ø cuerpo', 'DIAMETRO', '48.0300', '47.7800', '48.0300', 'Micrómetro'),
            ('F', 'Ø asiento 50.83 crítico', 'DIAMETRO', '50.8300', '50.8200', '50.8300', 'Micrómetro'),
            ('G', 'Ø sección A-A', 'DIAMETRO', '15.9300', '15.8800', '15.9300', 'Micrómetro'),
            ('H', 'Ø sección B-B', 'DIAMETRO', '41.5500', '41.4740', '41.5500', 'Micrómetro'),
            ('I', 'Ø sección C-C', 'DIAMETRO', '45.4400', '45.3640', '45.4400', 'Micrómetro'),
            ('J', 'Ø zona 35.81', 'DIAMETRO', '35.8100', '35.6100', '35.8100', 'Micrómetro'),
        ],
    }

    for nombre, puntos in datos.items():
        try:
            plantilla = Plantilla.objects.get(nombre=nombre)
        except Plantilla.DoesNotExist:
            continue
        for orden, (codigo, descripcion, tipo, nominal, minimo, maximo, instrumento) in enumerate(puntos, 1):
            punto, _ = Punto.objects.update_or_create(
                plantilla=plantilla,
                codigo=codigo,
                defaults={
                    'descripcion': descripcion,
                    'tipo': tipo,
                    'nominal': Decimal(nominal),
                    'minimo': Decimal(minimo),
                    'maximo': Decimal(maximo),
                    'unidad': 'mm',
                    'instrumento_sugerido': instrumento,
                    'critico': True,
                    'obligatorio': True,
                    'orden': orden,
                    'nota': 'Cota crítica según plano',
                },
            )
            # Las inspecciones creadas antes de esta migración estaban vacías.
            for inspeccion in Inspeccion.objects.filter(plantilla=plantilla):
                Medicion.objects.get_or_create(inspeccion=inspeccion, punto=punto)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('taller', '0007_metrologia_ejes')]
    operations = [migrations.RunPython(cargar_puntos_23t, noop)]
