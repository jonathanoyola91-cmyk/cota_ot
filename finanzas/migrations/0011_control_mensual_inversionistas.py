from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0010_alter_supplierinvoice_tipo_operacion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="FixedExpense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("periodo", models.DateField(help_text="Usar el primer día del mes", verbose_name="Mes")),
                ("categoria", models.CharField(choices=[("ARRIENDO","Arriendo"),("ENERGIA","Energía"),("AGUA","Agua"),("GAS","Gas"),("INTERNET","Internet / telefonía"),("NOMINA","Nómina"),("PARAFISCALES","Parafiscales / seguridad social"),("IMPUESTOS","Impuestos"),("SEGUROS","Seguros"),("SOFTWARE","Software / suscripciones"),("OTRO","Otro")], default="OTRO", max_length=20)),
                ("concepto", models.CharField(max_length=160)),
                ("valor", models.DecimalField(decimal_places=2, max_digits=14)),
                ("fecha_vencimiento", models.DateField(blank=True, null=True)),
                ("observacion", models.TextField(blank=True)),
                ("pagado", models.BooleanField(default=False)),
                ("fecha_pago", models.DateField(blank=True, null=True)),
                ("referencia_pago", models.CharField(blank=True, max_length=120)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fixed_expenses_created", to=settings.AUTH_USER_MODEL)),
                ("pagado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fixed_expenses_paid", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["fecha_vencimiento","concepto"]}),
        migrations.CreateModel(
            name="InvestorLoan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inversionista", models.CharField(max_length=160)),
                ("valor_prestado", models.DecimalField(decimal_places=2, max_digits=14)),
                ("interes_mensual", models.DecimalField(decimal_places=4, default=Decimal("0"), help_text="Porcentaje mensual. Ejemplo: 2.5 para 2,5%.", max_digits=7)),
                ("cuota_programada", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("fecha_prestamo", models.DateField(default=django.utils.timezone.localdate)),
                ("fecha_primera_cuota", models.DateField(blank=True, null=True)),
                ("activo", models.BooleanField(default=True)),
                ("observacion", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="investor_loans_created", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering":["-activo","inversionista"]}),
        migrations.CreateModel(
            name="InvestorPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_programada", models.DateField()),
                ("valor", models.DecimalField(decimal_places=2, max_digits=14)),
                ("pagado", models.BooleanField(default=False)),
                ("fecha_pago", models.DateField(blank=True, null=True)),
                ("referencia_pago", models.CharField(blank=True, max_length=120)),
                ("observacion", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("pagado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="investor_payments_paid", to=settings.AUTH_USER_MODEL)),
                ("prestamo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pagos", to="finanzas.investorloan")),
            ], options={"ordering":["fecha_programada","id"]}),
        migrations.AddIndex(model_name="fixedexpense", index=models.Index(fields=["periodo","pagado"], name="finanzas_fi_periodo_7e25e0_idx")),
        migrations.AddIndex(model_name="fixedexpense", index=models.Index(fields=["fecha_vencimiento"], name="finanzas_fi_fecha_v_97c35f_idx")),
        migrations.AddIndex(model_name="investorpayment", index=models.Index(fields=["fecha_programada","pagado"], name="finanzas_in_fecha_p_610d93_idx")),
    ]
