from django.core.management.base import BaseCommand
from presupuesto.sync import sync_presupuestos

class Command(BaseCommand):
    help = "Crea/actualiza presupuestos para todos los PAWs sin factura"

    def handle(self, *args, **options):
        n = sync_presupuestos()
        self.stdout.write(self.style.SUCCESS(f"OK. PAWs procesados: {n}"))