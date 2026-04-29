from paw_app.models import Paw

paws = Paw.objects.filter(cotizacion_id=1).order_by("id")

print("Total antes:", paws.count())

ids = list(paws.values_list("id", flat=True))

if len(ids) > 1:
    conservar = ids[0]
    eliminar = ids[1:]

    print("Conservando PAW ID:", conservar)
    print("Eliminando PAW IDs:", eliminar)

    eliminados = Paw.objects.filter(id__in=eliminar).delete()
    print("Resultado delete:", eliminados)

print("Total después:", Paw.objects.filter(cotizacion_id=1).count())