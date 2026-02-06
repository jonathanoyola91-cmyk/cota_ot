import pandas as pd
from django.core.management.base import BaseCommand
from bom.models import BomTemplate, BomTemplateItem


class Command(BaseCommand):
    help = "Importa un BOM Template desde Excel (encabezados en fila 8)"

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str)
        parser.add_argument("--nombre", type=str, required=True)

    def handle(self, *args, **options):
        archivo = options["archivo"]
        nombre = options["nombre"]

        template, created = BomTemplate.objects.get_or_create(nombre=nombre)

        if not created:
            self.stdout.write(
                self.style.WARNING("El template ya existe, se agregarán ítems nuevos.")
            )

        df = pd.read_excel(archivo, sheet_name=0, header=7)
        df.columns = df.columns.astype(str).str.strip().str.upper()

        count = 0

        for _, row in df.iterrows():
            descripcion = str(row.get("DESCRIPCION", "")).strip()

            if not descripcion or descripcion.lower() == "nan":
                continue

            plano = str(row.get("PLANO", "")).strip()
            codigo = str(row.get("PARTE NUMERO", "")).strip()
            unidad = str(row.get("UNIDAD", "")).strip()
            cantidad = row.get("CANTIDAD", 0) or 0
            observaciones = str(row.get("OBSERVACIONES", "")).strip()

            BomTemplateItem.objects.get_or_create(
                template=template,
                plano=plano,
                codigo=codigo,
                descripcion=descripcion,
                defaults={
                    "unidad": unidad,
                    "cantidad_estandar": cantidad,
                    "observaciones": observaciones,
                }
            )

            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Template '{template.nombre}' importado con {count} ítems."
            )
        )
