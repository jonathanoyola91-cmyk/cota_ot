from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('workorders', '0008_workorder_ensamble_confirmado_por'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='ensamble_confirmado_por',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                related_name='ensambles_confirmados'
            ),
        ),
    ]