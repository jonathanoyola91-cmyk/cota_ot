from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def cargar_plantillas(apps, schema_editor):
    Plantilla = apps.get_model("taller", "PlantillaEje")
    Punto = apps.get_model("taller", "PuntoMedicionEje")
    datos = [
        ("SHAFT K-38\"-8S ACR P-820-C", "OGSC-1007-AS-01-NP-01", "8", "ACERO M 303", [
            ("A", "Ø asiento extremo", 60.00, 60.00, 60.12), ("B", "Ø asiento", 65.00, 65.00, 65.025),
            ("C", "Ø asiento sello laberíntico", 58.00, 57.88, 57.98), ("D", "Ø asiento", 50.00, 49.88, 49.98),
            ("E", "Ø asiento rodamiento", 65.00, 65.00, 65.013), ("F", "Ø cuerpo / zona crítica", 38.10, 38.07, 38.10),
            ("G", "Ø ajuste H10", 38.28, 38.28, 38.38),
        ]),
        ("SHAFT K-35\"-8S TRAILER PAD CENTRAL", "OGSC-1007-AS-01-NP-01", "2", "ACERO M 303", [
            ("A", "Ø ajuste H10", 50.70, 50.70, 50.82), ("B", "Ø asiento", 65.00, 65.00, 65.025),
            ("C", "Ø asiento sello laberíntico", 58.00, 57.88, 57.98), ("D", "Ø asiento", 50.00, 49.88, 49.98),
            ("E", "Ø asiento rodamiento", 65.00, 65.00, 65.013), ("F", "Ø cuerpo / zona crítica", 38.10, 38.07, 38.10),
            ("G", "Ø ajuste H10", 38.28, 38.28, 38.38),
        ]),
        ("SHAFT K-27\"-8S CHB-4 UND 2", "", "1", "ACERO M 303", [
            ("A", "Ø asiento", 60.33, 60.30, 60.33), ("B", "Ø cuerpo / zona crítica", 44.45, 44.42, 44.45),
            ("C", "Ø asiento sello laberíntico", 58.00, 57.88, 57.98), ("D", "Ø asiento", 50.00, 49.88, 49.98),
            ("E", "Ø asiento rodamiento", 65.00, 65.00, 65.013), ("F", "Ø ajuste h7", 50.00, 49.975, 50.00),
        ]),
        ("SHAFT 23T 1 XT - HALF RING AND SLEEVES", "PLN0001520", "0", "", []),
        ("SHAFT 23T 1 XT V2 - 34.54", "PLN0001560", "1", "", []),
        ("SHAFT TC1 NVT - HALF RING AND SLEEVE", "PLN0001483", "0", "", [
            ("A", "Ø ajuste h10", 45.00, 44.90, 45.00), ("B", "Ø ajuste H11", 25.50, 25.50, 25.63),
            ("C", "Ø ajuste f8", 47.30, 47.24, 47.27), ("D", "Ø ajuste h7", 50.00, 49.97, 50.00),
            ("E", "Ø ajuste e9", 38.00, 37.89, 37.95),
        ]),
    ]
    for nombre, plano, rev, material, puntos in datos:
        plantilla, _ = Plantilla.objects.get_or_create(nombre=nombre, defaults={"codigo_plano": plano, "revision": rev, "material": material})
        for orden, (codigo, desc, nominal, minimo, maximo) in enumerate(puntos, 1):
            Punto.objects.get_or_create(plantilla=plantilla, codigo=codigo, defaults={"descripcion": desc, "tipo": "DIAMETRO", "nominal": nominal, "minimo": minimo, "maximo": maximo, "unidad": "mm", "instrumento_sugerido": "Micrómetro", "critico": True, "obligatorio": True, "orden": orden})


class Migration(migrations.Migration):
    dependencies = [("taller", "0006_alter_camarataller_estado_entregada"), migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("paw_app", "__first__")]
    operations = [
        migrations.CreateModel(name="InstrumentoMetrologico", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("nombre", models.CharField(max_length=120)), ("codigo", models.CharField(max_length=60, unique=True)), ("rango", models.CharField(blank=True, max_length=100)), ("resolucion", models.CharField(blank=True, max_length=60)), ("fecha_calibracion", models.DateField(blank=True, null=True)), ("fecha_vencimiento", models.DateField(blank=True, null=True)), ("activo", models.BooleanField(default=True))], options={"ordering": ["codigo"]}),
        migrations.CreateModel(name="PlantillaEje", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("nombre", models.CharField(max_length=180, unique=True)), ("codigo_plano", models.CharField(blank=True, max_length=120)), ("revision", models.CharField(blank=True, max_length=30)), ("material", models.CharField(blank=True, max_length=100)), ("activo", models.BooleanField(default=True)), ("observaciones", models.TextField(blank=True))], options={"verbose_name": "Plantilla metrológica de eje", "verbose_name_plural": "Plantillas metrológicas de ejes", "ordering": ["nombre"]}),
        migrations.CreateModel(name="PuntoMedicionEje", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("codigo", models.CharField(max_length=20)), ("descripcion", models.CharField(max_length=220)), ("tipo", models.CharField(choices=[("DIAMETRO", "Diámetro"), ("LONGITUD", "Longitud"), ("RUNOUT", "Runout"), ("ANCHO", "Ancho"), ("PROFUNDIDAD", "Profundidad"), ("OTRO", "Otro")], default="DIAMETRO", max_length=20)), ("nominal", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)), ("minimo", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)), ("maximo", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)), ("unidad", models.CharField(default="mm", max_length=20)), ("instrumento_sugerido", models.CharField(blank=True, max_length=120)), ("critico", models.BooleanField(default=True)), ("obligatorio", models.BooleanField(default=True)), ("orden", models.PositiveIntegerField(default=0)), ("nota", models.CharField(blank=True, max_length=250)), ("plantilla", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="puntos", to="taller.plantillaeje"))], options={"ordering": ["orden", "id"]}),
        migrations.CreateModel(name="InspeccionEje", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("serial_eje", models.CharField(blank=True, max_length=100)), ("estado", models.CharField(choices=[("BORRADOR", "En medición"), ("REVISADA", "Mediciones revisadas"), ("CERRADA", "Dictamen emitido")], default="BORRADOR", max_length=20)), ("resultado_dimensional", models.CharField(choices=[("PENDIENTE", "Pendiente"), ("CONFORME", "Conforme"), ("NO_CONFORME", "No conforme")], default="PENDIENTE", max_length=20)), ("dictamen", models.CharField(choices=[("PENDIENTE", "Pendiente"), ("APROBADO", "Aprobado"), ("CONCESION", "Aprobado bajo concesión"), ("MECANIZADO", "Requiere mecanizado"), ("RECHAZADO", "Rechazado")], default="PENDIENTE", max_length=20)), ("observaciones", models.TextField(blank=True)), ("fecha_revision", models.DateTimeField(blank=True, null=True)), ("creado_en", models.DateTimeField(auto_now_add=True)), ("actualizado_en", models.DateTimeField(auto_now=True)), ("camara", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inspecciones_eje", to="taller.camarataller")), ("paw", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inspecciones_eje", to="paw_app.paw")), ("plantilla", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inspecciones", to="taller.plantillaeje")), ("realizado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inspecciones_eje_realizadas", to=settings.AUTH_USER_MODEL)), ("revisado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inspecciones_eje_revisadas", to=settings.AUTH_USER_MODEL))], options={"ordering": ["-creado_en"]}),
        migrations.CreateModel(name="MedicionEje", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("valor", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)), ("instrumento_texto", models.CharField(blank=True, max_length=120)), ("observacion", models.CharField(blank=True, max_length=250)), ("evidencia", models.ImageField(blank=True, null=True, upload_to="taller/metrologia/ejes/%Y/%m/")), ("actualizado_en", models.DateTimeField(auto_now=True)), ("inspeccion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mediciones", to="taller.inspeccioneje")), ("instrumento", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mediciones", to="taller.instrumentometrologico")), ("punto", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mediciones", to="taller.puntomedicioneje"))], options={"ordering": ["punto__orden", "id"]}),
        migrations.AddConstraint(model_name="puntomedicioneje", constraint=models.UniqueConstraint(fields=("plantilla", "codigo"), name="uniq_punto_eje_plantilla")),
        migrations.AddConstraint(model_name="medicioneje", constraint=models.UniqueConstraint(fields=("inspeccion", "punto"), name="uniq_medicion_punto_inspeccion_eje")),
        migrations.RunPython(cargar_plantillas, migrations.RunPython.noop),
    ]
