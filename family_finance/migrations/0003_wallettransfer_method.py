from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("family_finance", "0002_add_household_subscriptions_category")]

    operations = [
        migrations.AddField(
            model_name="wallettransfer",
            name="method",
            field=models.CharField(
                choices=[("NEQUI", "Nequi"), ("CASH", "Efectivo")],
                default="NEQUI",
                max_length=10,
                verbose_name="forma de entrega",
            ),
        ),
    ]
