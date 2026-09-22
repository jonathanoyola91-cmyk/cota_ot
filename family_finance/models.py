from calendar import month_name
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


ZERO = Decimal("0.00")
MONEY_VALIDATORS = [MinValueValidator(ZERO)]


class Household(models.Model):
    name = models.CharField("nombre de la familia", max_length=120)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_households",
    )
    currency = models.CharField(max_length=3, default="COP")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "familia"
        verbose_name_plural = "familias"

    def __str__(self):
        return self.name


class FamilyMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Propietario y aprobador"
        ADMIN = "ADMIN", "Administrador familiar"
        CHILD = "CHILD", "Hijo/a"

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="family_membership",
    )
    display_name = models.CharField("nombre", max_length=100)
    role = models.CharField(max_length=10, choices=Role.choices)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "miembro familiar"
        verbose_name_plural = "miembros familiares"
        ordering = ["role", "display_name"]

    def __str__(self):
        return f"{self.display_name} · {self.get_role_display()}"

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def can_manage(self):
        return self.role in {self.Role.OWNER, self.Role.ADMIN}

    @property
    def can_approve(self):
        return self.role == self.Role.OWNER


class Category(models.Model):
    class Kind(models.TextChoices):
        FIXED = "FIXED", "Gasto fijo"
        VARIABLE = "VARIABLE", "Gasto variable"
        CHILD = "CHILD", "Presupuesto personal"
        DEBT = "DEBT", "Deuda"
        SAVINGS = "SAVINGS", "Ahorro"

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    color = models.CharField(max_length=7, default="#2563eb")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["household", "name", "kind"],
                name="unique_family_category",
            )
        ]

    def __str__(self):
        return self.name


class MonthlyPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "En preparación"
        ACTIVE = "ACTIVE", "Activo"
        CLOSED = "CLOSED", "Cerrado"

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="monthly_plans"
    )
    year = models.PositiveSmallIntegerField("año")
    month = models.PositiveSmallIntegerField("mes")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    savings_target = models.DecimalField(
        "meta de ahorro", max_digits=14, decimal_places=2, default=ZERO,
        validators=MONEY_VALIDATORS,
    )
    notes = models.TextField("notas", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="family_plans"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["household", "year", "month"],
                name="unique_family_month",
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1, month__lte=12),
                name="valid_family_month",
            ),
        ]

    def __str__(self):
        return f"{self.household} · {self.month:02d}/{self.year}"

    @property
    def month_label(self):
        spanish = (
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        )
        return f"{spanish[self.month]} {self.year}"


class Income(models.Model):
    plan = models.ForeignKey(MonthlyPlan, on_delete=models.CASCADE, related_name="incomes")
    name = models.CharField("ingreso", max_length=120)
    expected_amount = models.DecimalField(
        "valor esperado", max_digits=14, decimal_places=2, validators=MONEY_VALIDATORS
    )
    received_amount = models.DecimalField(
        "valor recibido", max_digits=14, decimal_places=2, default=ZERO,
        validators=MONEY_VALIDATORS,
    )
    expected_date = models.DateField("fecha esperada", blank=True, null=True)
    received_date = models.DateField("fecha recibida", blank=True, null=True)
    notes = models.CharField("notas", max_length=250, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expected_date", "id"]

    def __str__(self):
        return self.name


class FixedExpense(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        PAID = "PAID", "Pagado"
        OVERDUE = "OVERDUE", "Vencido"

    plan = models.ForeignKey(
        MonthlyPlan, on_delete=models.CASCADE, related_name="fixed_expenses"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField("obligación", max_length=120)
    budgeted_amount = models.DecimalField(
        "valor presupuestado", max_digits=14, decimal_places=2,
        validators=MONEY_VALIDATORS,
    )
    paid_amount = models.DecimalField(
        "valor pagado", max_digits=14, decimal_places=2, default=ZERO,
        validators=MONEY_VALIDATORS,
    )
    due_date = models.DateField("vencimiento", blank=True, null=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    recurring = models.BooleanField("repetir cada mes", default=True)
    notes = models.CharField("notas", max_length=250, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["due_date", "name"]

    def __str__(self):
        return self.name


class BudgetAllocation(models.Model):
    plan = models.ForeignKey(
        MonthlyPlan, on_delete=models.CASCADE, related_name="allocations"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    planned_amount = models.DecimalField(
        "meta de gasto", max_digits=14, decimal_places=2, validators=MONEY_VALIDATORS
    )
    notes = models.CharField("meta o explicación", max_length=250, blank=True)

    class Meta:
        ordering = ["category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "category"], name="unique_month_category_budget"
            )
        ]

    def __str__(self):
        return f"{self.category}: {self.planned_amount}"


class PersonalBudget(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        SUBMITTED = "SUBMITTED", "Enviado para aprobación"
        APPROVED = "APPROVED", "Aprobado"
        CHANGES = "CHANGES", "Requiere ajustes"
        REJECTED = "REJECTED", "Rechazado"

    plan = models.ForeignKey(
        MonthlyPlan, on_delete=models.CASCADE, related_name="personal_budgets"
    )
    member = models.ForeignKey(
        FamilyMembership, on_delete=models.CASCADE, related_name="personal_budgets"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    child_message = models.TextField("mensaje", blank=True)
    reviewer_comment = models.TextField("comentario del aprobador", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True,
        related_name="reviewed_family_budgets",
    )
    submitted_at = models.DateTimeField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "member"], name="unique_personal_month_budget"
            )
        ]

    @property
    def requested_total(self):
        return self.lines.aggregate(total=Sum("requested_amount"))["total"] or ZERO

    @property
    def approved_total(self):
        return self.lines.aggregate(total=Sum("approved_amount"))["total"] or ZERO

    def __str__(self):
        return f"{self.member.display_name} · {self.plan.month_label}"


class PersonalBudgetLine(models.Model):
    budget = models.ForeignKey(
        PersonalBudget, on_delete=models.CASCADE, related_name="lines"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    description = models.CharField("para qué lo necesitas", max_length=150)
    requested_amount = models.DecimalField(
        "valor solicitado", max_digits=14, decimal_places=2,
        validators=MONEY_VALIDATORS,
    )
    approved_amount = models.DecimalField(
        "valor aprobado", max_digits=14, decimal_places=2, default=ZERO,
        validators=MONEY_VALIDATORS,
    )
    notes = models.CharField("explicación", max_length=250, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.description


class ExtraRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        APPROVED = "APPROVED", "Aprobada"
        REJECTED = "REJECTED", "Rechazada"

    plan = models.ForeignKey(
        MonthlyPlan, on_delete=models.CASCADE, related_name="extra_requests"
    )
    member = models.ForeignKey(
        FamilyMembership, on_delete=models.CASCADE, related_name="extra_requests"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    description = models.CharField("qué deseas comprar", max_length=150)
    requested_amount = models.DecimalField(
        "valor solicitado", max_digits=14, decimal_places=2,
        validators=MONEY_VALIDATORS,
    )
    approved_amount = models.DecimalField(
        "valor aprobado", max_digits=14, decimal_places=2, default=ZERO,
        validators=MONEY_VALIDATORS,
    )
    reason = models.TextField("por qué lo necesitas")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    reviewer_comment = models.TextField("respuesta", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True,
        related_name="reviewed_extra_requests",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.description


class Expense(models.Model):
    class Source(models.TextChoices):
        NEQUI = "NEQUI", "Nequi"
        CASH = "CASH", "Efectivo"
        CARD = "CARD", "Tarjeta"
        BANK = "BANK", "Cuenta bancaria"

    plan = models.ForeignKey(MonthlyPlan, on_delete=models.CASCADE, related_name="expenses")
    member = models.ForeignKey(
        FamilyMembership, on_delete=models.PROTECT, related_name="expenses"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    description = models.CharField("descripción", max_length=150)
    amount = models.DecimalField(
        "valor", max_digits=14, decimal_places=2, validators=MONEY_VALIDATORS
    )
    date = models.DateField("fecha")
    source = models.CharField(max_length=10, choices=Source.choices)
    receipt = models.FileField("comprobante", upload_to="familia/comprobantes/%Y/%m/", blank=True)
    notes = models.CharField("notas", max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.description} · {self.amount}"


class WalletTransfer(models.Model):
    class Status(models.TextChoices):
        SENT = "SENT", "Enviado"
        CONFIRMED = "CONFIRMED", "Confirmado por el hijo"

    plan = models.ForeignKey(
        MonthlyPlan, on_delete=models.CASCADE, related_name="wallet_transfers"
    )
    member = models.ForeignKey(
        FamilyMembership, on_delete=models.CASCADE, related_name="wallet_transfers"
    )
    amount = models.DecimalField(
        "valor transferido", max_digits=14, decimal_places=2,
        validators=MONEY_VALIDATORS,
    )
    date = models.DateField("fecha")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    note = models.CharField("nota", max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"Nequi {self.member.display_name} · {self.amount}"


class SavingsGoal(models.Model):
    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="savings_goals"
    )
    name = models.CharField("meta", max_length=120)
    target_amount = models.DecimalField(
        "valor objetivo", max_digits=14, decimal_places=2, validators=MONEY_VALIDATORS
    )
    saved_amount = models.DecimalField(
        "valor ahorrado", max_digits=14, decimal_places=2, default=ZERO,
        validators=MONEY_VALIDATORS,
    )
    target_date = models.DateField("fecha objetivo", blank=True, null=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["target_date", "name"]

    @property
    def progress_percent(self):
        if not self.target_amount:
            return 0
        return min(100, round((self.saved_amount / self.target_amount) * 100))

    def __str__(self):
        return self.name
