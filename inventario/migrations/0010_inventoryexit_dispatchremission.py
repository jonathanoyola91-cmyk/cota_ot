from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_remission_sequence(apps, schema_editor):
    apps.get_model("inventario", "RemissionSequence").objects.get_or_create(pk=1, defaults={"ultimo": 1511})


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0009_inventoryreception_notificacion_100_en_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryExit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("destino", models.CharField(max_length=160)),
                ("solicitado_por", models.CharField(blank=True, max_length=160)),
                ("recibido_por", models.CharField(blank=True, max_length=160)),
                ("motivo", models.TextField(blank=True)),
                ("comentarios", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="salidas_inventario_creadas", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="RemissionSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ultimo", models.PositiveIntegerField(default=1511)),
            ],
        ),
        migrations.CreateModel(
            name="DispatchRemission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("consecutivo", models.PositiveIntegerField(unique=True)),
                ("cliente", models.CharField(max_length=200)),
                ("nit", models.CharField(blank=True, max_length=60)),
                ("contacto_cliente", models.CharField(blank=True, max_length=160)),
                ("telefono_cliente", models.CharField(blank=True, max_length=80)),
                ("direccion_cliente", models.CharField(blank=True, max_length=260)),
                ("fecha_envio", models.DateField()),
                ("contacto_envio", models.CharField(blank=True, max_length=160)),
                ("telefono_envio", models.CharField(blank=True, max_length=80)),
                ("direccion_envio", models.CharField(blank=True, max_length=260)),
                ("tipo_vehiculo", models.CharField(blank=True, max_length=100)),
                ("placa", models.CharField(blank=True, max_length=40)),
                ("nombre_conductor", models.CharField(blank=True, max_length=160)),
                ("celular_conductor", models.CharField(blank=True, max_length=80)),
                ("observaciones", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="remisiones_salida_creadas", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="InventoryExitLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("catalogo", models.CharField(blank=True, default="", max_length=20)),
                ("catalogo_item_id", models.PositiveIntegerField(blank=True, null=True)),
                ("codigo", models.CharField(blank=True, default="", max_length=80)),
                ("descripcion", models.CharField(max_length=300)),
                ("unidad", models.CharField(blank=True, default="", max_length=30)),
                ("cantidad", models.DecimalField(decimal_places=3, default=1, max_digits=12)),
                ("numero_serial", models.CharField(blank=True, default="", max_length=120)),
                ("salida", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lineas", to="inventario.inventoryexit")),
            ],
        ),
        migrations.CreateModel(
            name="DispatchRemissionLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("catalogo", models.CharField(blank=True, default="", max_length=20)),
                ("catalogo_item_id", models.PositiveIntegerField(blank=True, null=True)),
                ("descripcion", models.CharField(max_length=300)),
                ("cantidad", models.DecimalField(decimal_places=3, default=1, max_digits=12)),
                ("unidad", models.CharField(blank=True, default="UND", max_length=30)),
                ("parte_numero", models.CharField(blank=True, default="", max_length=100)),
                ("numero_serial", models.CharField(blank=True, default="", max_length=120)),
                ("remision", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lineas", to="inventario.dispatchremission")),
            ],
        ),
        migrations.RunPython(
            seed_remission_sequence,
            migrations.RunPython.noop,
        ),
    ]
