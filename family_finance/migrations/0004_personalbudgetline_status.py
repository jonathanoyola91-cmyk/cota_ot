from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("family_finance", "0003_wallettransfer_method")]

    operations = [
        migrations.AddField(
            model_name="personalbudgetline",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pendiente"),
                    ("APPROVED", "Aprobada"),
                    ("REJECTED", "Rechazada"),
                ],
                default="PENDING",
                max_length=10,
                verbose_name="decisión",
            ),
        ),
    ]
