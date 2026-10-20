"""Audita reservas activas de solicitudes PAW cerradas. No modifica datos."""
import csv
from django.core.management.base import BaseCommand
from inventario.models import InventoryReservation


class Command(BaseCommand):
    help = 'Exporta reservas activas de PAW cerrados para conciliación y autorización.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default='auditoria_reservas_cerradas.csv')

    def handle(self, *args, **options):
        qs = (InventoryReservation.objects.select_related('stock', 'purchase_request', 'purchase_line')
              .filter(estado=InventoryReservation.Estado.ACTIVA,
                      purchase_request__origen='PAW',
                      purchase_request__estado='CERRADA')
              .order_by('purchase_request__paw_numero', 'stock__codigo', 'pk'))
        headers = ['reserva_id', 'paw', 'compra_id', 'codigo', 'empresa', 'reservado_original',
                   'consumido', 'pendiente_teorico', 'fisico_stock', 'reservado_stock',
                   'estado_compra', 'revision_pendiente', 'observacion']
        count = 0
        with open(options['csv'], 'w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            for r in qs.iterator():
                compra, stock = r.purchase_request, r.stock
                pendiente = r.cantidad - r.cantidad_consumida
                writer.writerow([r.pk, compra.paw_numero, compra.pk, stock.codigo, stock.empresa,
                                 r.cantidad, r.cantidad_consumida, pendiente,
                                 stock.cantidad_fisica, stock.cantidad_reservada,
                                 compra.estado, compra.revision_reservas_pendiente, r.observacion])
                count += 1
        self.stdout.write(self.style.SUCCESS(f'{count} reservas auditadas; reporte: {options["csv"]}. Sin modificaciones.'))
