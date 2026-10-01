from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("campo", "0010_fieldservicebonusclaim_gastos_personales"),
    ]

    operations = [
        migrations.AddField(
            model_name="fieldservice",
            name="especialista_lider_usuario",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="servicios_campo_como_lider", to=settings.AUTH_USER_MODEL,
                verbose_name="Especialista líder",
            ),
        ),
        migrations.AddField(
            model_name="fieldservice",
            name="especialista_apoyo_usuario",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="servicios_campo_como_apoyo", to=settings.AUTH_USER_MODEL,
                verbose_name="Especialista apoyo",
            ),
        ),
    ]
