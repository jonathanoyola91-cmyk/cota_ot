from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hse", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="hserequest",
            name="motivo_entrega",
            field=models.CharField(
                choices=[
                    ("VU", "Expiró su vida útil"),
                    ("RP", "Reposición por pérdida"),
                    ("CD", "Cambio por deterioro"),
                    ("PE", "Primera entrega"),
                ],
                default="PE",
                max_length=2,
            ),
        ),
    ]
