from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    BudgetAllocation,
    Category,
    Debt,
    DebtPayment,
    Expense,
    ExtraRequest,
    FamilyMembership,
    FixedExpense,
    Household,
    Income,
    MonthlyPlan,
    PersonalBudget,
    PersonalBudgetLine,
    SavingsGoal,
    WalletTransfer,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class HouseholdSetupForm(StyledModelForm):
    class Meta:
        model = Household
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Familia Oyola"})}


class TrialFamilyCreationForm(UserCreationForm):
    family_name = forms.CharField(
        label="Nombre de la familia", max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Familia Pérez"}),
    )
    display_name = forms.CharField(
        label="Nombre del cabeza de familia", max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Carlos Pérez"}),
    )
    email = forms.EmailField(label="Correo (opcional)", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "email", "family_name", "display_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["username"].help_text = "Este será el usuario con el que ingresará la familia."


class FamilyMemberCreationForm(UserCreationForm):
    display_name = forms.CharField(label="Nombre para mostrar", max_length=100)
    role = forms.ChoiceField(
        label="Rol",
        choices=[
            (FamilyMembership.Role.ADMIN, "Esposa/o · administra el presupuesto"),
            (FamilyMembership.Role.CHILD, "Hijo/a · administra solo su presupuesto"),
        ],
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "display_name", "role", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["username"].help_text = "Se usará para ingresar a IMPETUS Control."


class ExistingFamilyMemberForm(forms.Form):
    user = forms.ModelChoiceField(label="Usuario existente", queryset=User.objects.none())
    display_name = forms.CharField(label="Nombre para mostrar", max_length=100)
    role = forms.ChoiceField(
        label="Rol familiar",
        choices=[
            (FamilyMembership.Role.ADMIN, "Esposa/o · administra el presupuesto"),
            (FamilyMembership.Role.CHILD, "Hijo/a · administra solo su presupuesto"),
        ],
    )

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        existing_members = household.memberships.values_list("user_id", flat=True)
        self.fields["user"].queryset = User.objects.exclude(pk__in=existing_members).order_by(
            "first_name", "username"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class MonthlyPlanForm(StyledModelForm):
    copy_previous = forms.BooleanField(
        label="Copiar gastos fijos y metas del mes anterior", required=False, initial=True
    )

    class Meta:
        model = MonthlyPlan
        fields = ["year", "month", "savings_target", "notes"]
        widgets = {
            "month": forms.Select(choices=[
                (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
                (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
                (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
            ]),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = date.today()
        self.fields["year"].initial = today.year
        self.fields["month"].initial = today.month


class IncomeForm(StyledModelForm):
    class Meta:
        model = Income
        fields = ["name", "expected_amount", "received_amount", "expected_date", "received_date", "notes"]
        widgets = {
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "received_date": forms.DateInput(attrs={"type": "date"}),
        }


class FixedExpenseForm(StyledModelForm):
    class Meta:
        model = FixedExpense
        fields = ["category", "name", "budgeted_amount", "paid_amount", "due_date", "status", "recurring", "notes"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household:
            self.fields["category"].queryset = household.categories.filter(
                kind__in=[Category.Kind.FIXED, Category.Kind.DEBT], active=True
            )


class DebtForm(StyledModelForm):
    class Meta:
        model = Debt
        fields = [
            "category", "name", "bank", "opening_balance", "monthly_payment",
            "monthly_interest_rate", "active",
        ]

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household:
            self.fields["category"].queryset = household.categories.filter(
                kind=Category.Kind.DEBT, active=True
            )


class DebtPaymentForm(StyledModelForm):
    class Meta:
        model = DebtPayment
        fields = ["payment_amount", "principal_amount", "interest_amount", "payment_date", "note"]
        widgets = {"payment_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_date"].initial = date.today()

    def clean(self):
        cleaned = super().clean()
        total = cleaned.get("payment_amount")
        principal = cleaned.get("principal_amount")
        interest = cleaned.get("interest_amount") or 0
        if total is not None and principal is not None and principal + interest > total:
            raise forms.ValidationError(
                "El capital más los intereses no puede superar el valor pagado."
            )
        return cleaned


class AllocationForm(StyledModelForm):
    class Meta:
        model = BudgetAllocation
        fields = ["category", "planned_amount", "notes"]

    def __init__(self, *args, household=None, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household:
            qs = household.categories.filter(kind=Category.Kind.VARIABLE, active=True)
            if plan and not self.instance.pk:
                qs = qs.exclude(budgetallocation__plan=plan)
            self.fields["category"].queryset = qs


class PersonalBudgetHeaderForm(StyledModelForm):
    class Meta:
        model = PersonalBudget
        fields = ["child_message"]
        widgets = {"child_message": forms.Textarea(attrs={"rows": 2, "placeholder": "Cuéntale a papá qué quieres lograr este mes"})}


class PersonalBudgetLineForm(StyledModelForm):
    class Meta:
        model = PersonalBudgetLine
        fields = ["category", "description", "requested_amount", "notes"]

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household:
            self.fields["category"].queryset = household.categories.filter(
                kind__in=[Category.Kind.CHILD, Category.Kind.VARIABLE], active=True
            )


class ExpenseForm(StyledModelForm):
    class Meta:
        model = Expense
        fields = ["category", "description", "amount", "date", "source", "receipt", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, household=None, child=False, **kwargs):
        super().__init__(*args, **kwargs)
        if household:
            kinds = [Category.Kind.CHILD, Category.Kind.VARIABLE] if child else list(Category.Kind.values)
            self.fields["category"].queryset = household.categories.filter(kind__in=kinds, active=True)
        self.fields["date"].initial = date.today()


class ExtraRequestForm(StyledModelForm):
    class Meta:
        model = ExtraRequest
        fields = ["category", "description", "requested_amount", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, household=None, child=False, **kwargs):
        super().__init__(*args, **kwargs)
        if household:
            kinds = [Category.Kind.CHILD, Category.Kind.VARIABLE] if child else list(Category.Kind.values)
            self.fields["category"].queryset = household.categories.filter(kind__in=kinds, active=True)


class WalletTransferForm(StyledModelForm):
    class Meta:
        model = WalletTransfer
        fields = ["member", "amount", "method", "date", "note"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        if household:
            self.fields["member"].queryset = household.memberships.filter(
                role=FamilyMembership.Role.CHILD, active=True
            )
        self.fields["date"].initial = date.today()


class SavingsGoalForm(StyledModelForm):
    class Meta:
        model = SavingsGoal
        fields = ["name", "target_amount", "saved_amount", "target_date"]
        widgets = {"target_date": forms.DateInput(attrs={"type": "date"})}
