from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("paw_app", "0013_alter_paw_public_token")]

    operations = [
        migrations.AlterField(
            model_name="paw",
            name="estado_operativo",
            field=models.CharField(
                choices=[
                    ("PAW_CREADO", "PAW creado"),
                    ("OT_CREADA", "OT creada"),
                    ("BOM_CREADO", "BOM creado"),
                    ("EN_REVISION_INVENTARIO", "En revisión de inventario"),
                    ("EN_COMPRAS", "En compras"),
                    ("EN_FINANZAS", "En finanzas"),
                    ("EN_APROBACION", "En aprobación"),
                    ("PAGO_OK", "Pago OK"),
                    ("MATERIAL_RECIBIDO", "Material recibido"),
                    ("ENTREGADO_TALLER", "Entregado a taller"),
                    ("PRODUCTO_OK", "Producto OK"),
                    ("EN_FACTURACION", "En facturación"),
                    ("FACTURADO", "Facturado"),
                    ("RADICADO", "Radicado"),
                ],
                default="PAW_CREADO",
                max_length=30,
            ),
        ),
    ]
