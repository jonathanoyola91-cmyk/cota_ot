from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0020_receptionwarehousetransfer"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name="DeliveryPendingCancellation",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("cantidad", models.DecimalField(max_digits=12, decimal_places=3)),
            ("motivo", models.TextField()),
            ("creado_en", models.DateTimeField(auto_now_add=True)),
            ("creado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("delivery_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cancelaciones", to="inventario.workshopdeliveryline")),
        ],
    )]
