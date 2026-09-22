import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("family_finance", "0004_personalbudgetline_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Debt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="nombre de la deuda")),
                ("bank", models.CharField(blank=True, max_length=120, verbose_name="banco o entidad")),
                ("opening_balance", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))], verbose_name="saldo pendiente al iniciar")),
                ("monthly_payment", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))], verbose_name="cuota mensual")),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="family_finance.category")),
                ("household", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="debts", to="family_finance.household")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="DebtPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_amount", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))], verbose_name="valor pagado")),
                ("principal_amount", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))], verbose_name="abono a capital")),
                ("interest_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))], verbose_name="intereses incluidos")),
                ("payment_date", models.DateField(verbose_name="fecha de pago")),
                ("note", models.CharField(blank=True, max_length=250, verbose_name="nota")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("debt", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="family_finance.debt")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="debt_payments", to="family_finance.monthlyplan")),
            ],
            options={"ordering": ["-payment_date", "-id"]},
        ),
    ]
