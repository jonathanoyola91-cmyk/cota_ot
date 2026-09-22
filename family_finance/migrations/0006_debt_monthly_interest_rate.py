from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("family_finance", "0005_debt_debtpayment")]

    operations = [
        migrations.AddField(
            model_name="debt",
            name="monthly_interest_rate",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.00"),
                help_text="Use la tasa mes vencido. Para un préstamo sin intereses escriba 0.",
                max_digits=7,
                validators=[MinValueValidator(Decimal("0.00"))],
                verbose_name="tasa de interés mensual (%)",
            ),
        ),
    ]
