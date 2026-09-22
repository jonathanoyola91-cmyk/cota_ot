from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import family_messages as messages
from .decorators import family_member_required, manager_required, owner_required
from .forms import (
    AllocationForm, DebtForm, DebtPaymentForm, ExpenseForm, ExistingFamilyMemberForm,
    ExtraRequestForm, FamilyMemberCreationForm,
    FixedExpenseForm, HouseholdSetupForm, IncomeForm, MonthlyPlanForm,
    PersonalBudgetHeaderForm, PersonalBudgetLineForm, SavingsGoalForm,
    TrialFamilyCreationForm, WalletTransferForm,
)
from .models import (
    BudgetAllocation, Category, Debt, DebtPayment, Expense, ExtraRequest, FamilyMembership,
    FixedExpense, Household, Income, MonthlyPlan, PersonalBudget,
    PersonalBudgetLine, SavingsGoal, WalletTransfer, ZERO,
)
from .services import (
    category_rows, personal_summary, plan_totals, seed_categories,
    smart_recommendations, spending_ranking,
)


def _selected_plan(request):
    qs = request.household.monthly_plans.all()
    plan_id = request.GET.get("plan") or request.POST.get("plan")
    if plan_id:
        return get_object_or_404(qs, pk=plan_id)
    today = date.today()
    return qs.filter(year=today.year, month=today.month).first() or qs.first()


def _plan_for_household(request, plan_id):
    return get_object_or_404(request.household.monthly_plans, pk=plan_id)


def _money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount >= ZERO else None


@login_required
def setup_household(request):
    if hasattr(request.user, "family_membership"):
        return redirect("family_finance:dashboard")
    if not request.user.is_superuser:
        raise Http404
    form = HouseholdSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            household = form.save(commit=False)
            household.owner = request.user
            household.save()
            FamilyMembership.objects.create(
                household=household,
                user=request.user,
                display_name=request.user.get_short_name() or request.user.username,
                role=FamilyMembership.Role.OWNER,
            )
            seed_categories(household)
        messages.success(request, "La familia quedó configurada. Ya puedes crear el primer mes.")
        return redirect("family_finance:dashboard")
    return render(request, "family_finance/setup.html", {"form": form})


@login_required
def trial_family_create(request):
    if not request.user.is_superuser:
        raise Http404
    form = TrialFamilyCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.first_name = form.cleaned_data["display_name"]
            user.is_staff = False
            user.is_superuser = False
            user.save()
            household = Household.objects.create(
                name=form.cleaned_data["family_name"], owner=user,
            )
            FamilyMembership.objects.create(
                household=household, user=user,
                display_name=form.cleaned_data["display_name"],
                role=FamilyMembership.Role.OWNER,
            )
            seed_categories(household)
        messages.success(
            request,
            f"Acceso creado para {form.cleaned_data['display_name']}. Envíale el enlace /familia/ y el usuario que registraste.",
        )
        return redirect("family_finance:dashboard")
    return render(request, "family_finance/form.html", {
        "form": form,
        "title": "Crear familia de prueba",
        "submit_label": "Crear acceso familiar",
        "helper": "Este usuario será dueño solo de su propia familia; no tendrá permisos de IMPETUS Control.",
    })


@family_member_required
def dashboard(request):
    membership = request.family_membership
    plan = _selected_plan(request)
    context = {
        "membership": membership,
        "household": request.household,
        "plan": plan,
        "plans": request.household.monthly_plans.all()[:18],
        "goals": request.household.savings_goals.filter(active=True),
    }
    if not plan:
        return render(request, "family_finance/dashboard.html", context)

    context["category_rows"] = category_rows(plan)
    context["pending_requests_count"] = plan.extra_requests.filter(
        status=ExtraRequest.Status.PENDING
    ).count()
    if membership.can_manage:
        personal_members = request.household.memberships.filter(
            active=True,
        ).exclude(role=FamilyMembership.Role.OWNER)
        owner_member = request.household.memberships.get(role=FamilyMembership.Role.OWNER)
        context.update({
            "totals": plan_totals(plan),
            "spending_ranking": spending_ranking(plan),
            "smart_recommendations": smart_recommendations(plan),
            "pending_budgets": plan.personal_budgets.filter(
                status=PersonalBudget.Status.SUBMITTED
            ).select_related("member"),
            "pending_requests": plan.extra_requests.filter(
                status=ExtraRequest.Status.PENDING
            ).select_related("member", "category"),
            "personal_summaries": [
                {"member": member, **personal_summary(plan, member)}
                for member in personal_members
            ],
            "my_personal": personal_summary(plan, membership),
            "owner_personal": personal_summary(plan, owner_member),
            "fixed_expenses": plan.fixed_expenses.select_related("category"),
            "debts": request.household.debts.filter(active=True).select_related("category"),
            "incomes": plan.incomes.select_related("created_by"),
        })
    else:
        context.update({
            "personal": personal_summary(plan, membership),
            "my_requests": plan.extra_requests.filter(member=membership)[:5],
            "my_transfers": plan.wallet_transfers.filter(member=membership)[:5],
            "my_expenses": plan.expenses.filter(member=membership)[:8],
        })
    return render(request, "family_finance/dashboard.html", context)


@family_member_required
def install_access(request):
    return render(request, "family_finance/install_access.html")


@owner_required
def member_create(request):
    form = FamilyMemberCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            FamilyMembership.objects.create(
                household=request.household,
                user=user,
                display_name=form.cleaned_data["display_name"],
                role=form.cleaned_data["role"],
            )
        messages.success(request, f"{form.cleaned_data['display_name']} ya puede ingresar.")
        return redirect("family_finance:dashboard")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Agregar integrante", "submit_label": "Crear acceso"
    })


@owner_required
def member_link_existing(request):
    if not request.user.is_superuser:
        raise Http404
    form = ExistingFamilyMemberForm(request.POST or None, household=request.household)
    if request.method == "POST" and form.is_valid():
        member = FamilyMembership.objects.create(
            household=request.household,
            user=form.cleaned_data["user"],
            display_name=form.cleaned_data["display_name"],
            role=form.cleaned_data["role"],
        )
        messages.success(request, f"{member.display_name} fue vinculado a la familia con su usuario actual.")
        return redirect("family_finance:dashboard")
    return render(request, "family_finance/form.html", {
        "form": form,
        "title": "Vincular usuario existente",
        "submit_label": "Vincular a la familia",
        "helper": "Úselo para su esposa si ya tiene acceso a IMPETUS Control.",
    })


@manager_required
def plan_create(request):
    form = MonthlyPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if request.household.monthly_plans.filter(
            year=form.cleaned_data["year"], month=form.cleaned_data["month"]
        ).exists():
            form.add_error(None, "Ese mes ya existe.")
        else:
            with transaction.atomic():
                plan = form.save(commit=False)
                plan.household = request.household
                plan.created_by = request.user
                plan.save()
                if form.cleaned_data["copy_previous"]:
                    previous = request.household.monthly_plans.exclude(pk=plan.pk).first()
                    if previous:
                        FixedExpense.objects.bulk_create([
                            FixedExpense(
                                plan=plan, category=item.category, name=item.name,
                                budgeted_amount=item.budgeted_amount, due_date=None,
                                recurring=item.recurring, notes=item.notes,
                                created_by=request.user,
                            )
                            for item in previous.fixed_expenses.filter(recurring=True)
                        ])
                        BudgetAllocation.objects.bulk_create([
                            BudgetAllocation(
                                plan=plan, category=item.category,
                                planned_amount=item.planned_amount, notes=item.notes,
                            )
                            for item in previous.allocations.all()
                        ], ignore_conflicts=True)
            messages.success(request, "Mes creado. Ahora registra los ingresos y obligaciones.")
            return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Crear presupuesto mensual", "submit_label": "Crear mes"
    })


@manager_required
def plan_copy_next_month(request, plan_id):
    if request.method != "POST":
        raise Http404
    previous = _plan_for_household(request, plan_id)
    year, month = previous.year, previous.month + 1
    if month == 13:
        year, month = year + 1, 1
    plan, created = MonthlyPlan.objects.get_or_create(
        household=request.household, year=year, month=month,
        defaults={"created_by": request.user, "savings_target": previous.savings_target},
    )
    if not created:
        messages.info(request, f"{plan.month_label} ya existe; no se duplicó información.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    FixedExpense.objects.bulk_create([
        FixedExpense(
            plan=plan, category=item.category, name=item.name,
            budgeted_amount=item.budgeted_amount, due_date=None,
            recurring=item.recurring, notes=item.notes, created_by=request.user,
        )
        for item in previous.fixed_expenses.filter(recurring=True)
    ])
    BudgetAllocation.objects.bulk_create([
        BudgetAllocation(plan=plan, category=item.category, planned_amount=item.planned_amount, notes=item.notes)
        for item in previous.allocations.all()
    ], ignore_conflicts=True)
    messages.success(request, f"{plan.month_label} fue creado con los gastos recurrentes y metas del mes anterior.")
    return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")


@manager_required
def income_create(request, plan_id):
    plan = _plan_for_household(request, plan_id)
    form = IncomeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.plan, item.created_by = plan, request.user
        item.save()
        messages.success(request, "Ingreso registrado.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": f"Ingreso · {plan.month_label}", "submit_label": "Guardar ingreso"
    })


@manager_required
def income_edit(request, item_id):
    item = get_object_or_404(Income, pk=item_id, plan__household=request.household)
    form = IncomeForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ingreso actualizado.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={item.plan_id}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Actualizar ingreso", "submit_label": "Guardar cambios"
    })


@manager_required
def fixed_expense_create(request, plan_id):
    plan = _plan_for_household(request, plan_id)
    form = FixedExpenseForm(request.POST or None, household=request.household)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.plan, item.created_by = plan, request.user
        item.save()
        messages.success(request, "Obligación mensual registrada.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": f"Gasto fijo o deuda · {plan.month_label}",
        "submit_label": "Guardar obligación",
    })


@manager_required
def fixed_expense_edit(request, item_id):
    item = get_object_or_404(FixedExpense, pk=item_id, plan__household=request.household)
    form = FixedExpenseForm(
        request.POST or None, instance=item, household=request.household
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Obligación actualizada.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={item.plan_id}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Actualizar gasto fijo o deuda",
        "submit_label": "Guardar cambios",
    })


@manager_required
def fixed_expense_delete(request, item_id):
    if request.method != "POST":
        raise Http404
    item = get_object_or_404(FixedExpense, pk=item_id, plan__household=request.household)
    plan_id = item.plan_id
    item.delete()
    messages.success(request, "La obligación fue eliminada de este mes.")
    return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan_id}")


@manager_required
def debt_create(request):
    plan = _selected_plan(request)
    if not plan:
        messages.error(request, "Primero debe existir un presupuesto mensual.")
        return redirect("family_finance:dashboard")
    form = DebtForm(request.POST or None, household=request.household)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            debt = form.save(commit=False)
            debt.household = request.household
            debt.save()
            FixedExpense.objects.get_or_create(
                plan=plan,
                name=f"Cuota · {debt.name}",
                defaults={
                    "category": debt.category,
                    "budgeted_amount": debt.monthly_payment,
                    "created_by": request.user,
                    "recurring": True,
                    "notes": f"Deuda vinculada: {debt.bank}".strip(": "),
                },
            )
        messages.success(request, "Deuda creada y cuota mensual agregada a gastos fijos.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Registrar deuda bancaria",
        "submit_label": "Crear deuda",
        "helper": "Registre el saldo que aún deben hoy; cada pago posterior reducirá ese valor.",
    })


@manager_required
def debt_edit(request, debt_id):
    debt = get_object_or_404(Debt, pk=debt_id, household=request.household)
    previous_name = debt.name
    form = DebtForm(request.POST or None, instance=debt, household=request.household)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            debt = form.save()
            FixedExpense.objects.filter(
                plan__household=request.household, name=f"Cuota · {previous_name}"
            ).update(
                name=f"Cuota · {debt.name}", category=debt.category,
                budgeted_amount=debt.monthly_payment,
            )
        messages.success(request, "Deuda actualizada. Sus cuotas mensuales fueron sincronizadas.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={_selected_plan(request).pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": f"Editar deuda · {debt.name}", "submit_label": "Guardar deuda",
        "helper": "La tasa debe ser mensual (%). Si el crédito no cobra intereses, escriba 0.",
    })


@manager_required
def debt_payment_create(request, debt_id):
    plan = _selected_plan(request)
    if not plan:
        return redirect("family_finance:dashboard")
    debt = get_object_or_404(Debt, pk=debt_id, household=request.household, active=True)
    form = DebtPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        payment = form.save(commit=False)
        if payment.principal_amount > debt.remaining_balance:
            form.add_error("principal_amount", "El abono a capital supera el saldo pendiente.")
        else:
            with transaction.atomic():
                payment.debt = debt
                payment.plan = plan
                payment.created_by = request.user
                payment.save()
                fixed, _ = FixedExpense.objects.get_or_create(
                    plan=plan,
                    name=f"Cuota · {debt.name}",
                    defaults={
                        "category": debt.category,
                        "budgeted_amount": debt.monthly_payment,
                        "created_by": request.user,
                        "recurring": True,
                        "notes": f"Deuda vinculada: {debt.bank}".strip(": "),
                    },
                )
                fixed.paid_amount += payment.payment_amount
                if fixed.paid_amount >= fixed.budgeted_amount:
                    fixed.status = FixedExpense.Status.PAID
                fixed.save(update_fields=["paid_amount", "status"])
            messages.success(request, "Pago registrado: el saldo de la deuda fue actualizado.")
            return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form,
        "title": f"Registrar pago · {debt.name}",
        "submit_label": "Registrar pago",
        "helper": f"Saldo pendiente actual: ${debt.remaining_balance:,.0f}. Indique cuánto del pago redujo capital.",
    })


@manager_required
def allocation_create(request, plan_id):
    plan = _plan_for_household(request, plan_id)
    form = AllocationForm(
        request.POST or None, household=request.household, plan=plan
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.plan = plan
        item.save()
        messages.success(request, "Meta de gasto registrada.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": f"Meta por categoría · {plan.month_label}",
        "submit_label": "Guardar meta",
    })


@manager_required
def allocation_edit(request, item_id):
    item = get_object_or_404(BudgetAllocation, pk=item_id, plan__household=request.household)
    form = AllocationForm(
        request.POST or None, instance=item, household=request.household, plan=item.plan
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Meta de gasto actualizada.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={item.plan_id}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Actualizar meta de gasto", "submit_label": "Guardar cambios"
    })


@family_member_required
def my_budget(request):
    membership = request.family_membership
    plan = _selected_plan(request)
    if not plan:
        messages.info(request, "Aún no hay un presupuesto mensual activo.")
        return redirect("family_finance:dashboard")
    budget, created = PersonalBudget.objects.get_or_create(
        plan=plan, member=membership,
        defaults={"status": PersonalBudget.Status.APPROVED}
        if membership.is_owner else {},
    )
    if membership.is_owner and budget.status != PersonalBudget.Status.APPROVED:
        budget.status = PersonalBudget.Status.APPROVED
        budget.save(update_fields=["status"])
    form = PersonalBudgetHeaderForm(request.POST or None, instance=budget)
    if request.method == "POST" and form.is_valid() and (membership.is_owner or budget.status in {
        PersonalBudget.Status.DRAFT, PersonalBudget.Status.CHANGES,
        PersonalBudget.Status.SUBMITTED,
    }):
        form.save()
        messages.success(request, "Tu mensaje quedó guardado.")
        return redirect(f"{redirect('family_finance:my_budget').url}?plan={plan.pk}")
    return render(request, "family_finance/my_budget.html", {
        "plan": plan, "budget": budget, "form": form,
        "summary": personal_summary(plan, membership),
        "is_owner_budget": membership.is_owner,
    })


@family_member_required
def budget_line_create(request):
    membership = request.family_membership
    plan = _selected_plan(request)
    if not plan:
        return redirect("family_finance:dashboard")
    budget, _ = PersonalBudget.objects.get_or_create(
        plan=plan, member=membership,
        defaults={"status": PersonalBudget.Status.APPROVED}
        if membership.is_owner else {},
    )
    if not membership.is_owner and budget.status not in {
        PersonalBudget.Status.DRAFT, PersonalBudget.Status.CHANGES,
        PersonalBudget.Status.SUBMITTED,
    }:
        messages.error(request, "Ese presupuesto ya fue aprobado y no se puede modificar.")
        return redirect("family_finance:my_budget")
    form = PersonalBudgetLineForm(request.POST or None, household=request.household)
    if request.method == "POST" and form.is_valid():
        line = form.save(commit=False)
        line.budget = budget
        if membership.is_owner:
            line.status = PersonalBudgetLine.Status.APPROVED
            line.approved_amount = line.requested_amount
        line.save()
        messages.success(request, "Compra personal agregada." if membership.is_owner else "Concepto agregado a tu propuesta.")
        return redirect(f"{redirect('family_finance:my_budget').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Agregar a mi presupuesto", "submit_label": "Agregar"
    })


@family_member_required
def budget_line_delete(request, line_id):
    if request.method != "POST":
        raise Http404
    line = get_object_or_404(
        PersonalBudgetLine,
        pk=line_id,
        budget__member=request.family_membership,
        budget__plan__household=request.household,
    )
    if not request.family_membership.is_owner and line.budget.status not in {
        PersonalBudget.Status.DRAFT, PersonalBudget.Status.CHANGES,
        PersonalBudget.Status.SUBMITTED,
    }:
        messages.error(request, "No se puede quitar un concepto después de aprobarlo.")
    else:
        plan_id = line.budget.plan_id
        line.delete()
        messages.success(request, "Concepto retirado de tu propuesta.")
        return redirect(f"{redirect('family_finance:my_budget').url}?plan={plan_id}")
    return redirect("family_finance:my_budget")


@family_member_required
def budget_submit(request):
    if request.method != "POST" or request.family_membership.role == FamilyMembership.Role.OWNER:
        raise Http404
    plan = _selected_plan(request)
    budget = get_object_or_404(
        PersonalBudget, plan=plan, member=request.family_membership
    )
    if not budget.lines.exists():
        messages.error(request, "Agrega al menos un concepto antes de enviarlo.")
    elif budget.status in {PersonalBudget.Status.DRAFT, PersonalBudget.Status.CHANGES}:
        budget.status = PersonalBudget.Status.SUBMITTED
        budget.submitted_at = timezone.now()
        budget.save(update_fields=["status", "submitted_at"])
        messages.success(request, "Presupuesto enviado a papá para aprobación.")
    return redirect(f"{redirect('family_finance:my_budget').url}?plan={plan.pk}")


@owner_required
def budget_review(request, budget_id):
    budget = get_object_or_404(
        PersonalBudget.objects.select_related("member", "plan"),
        pk=budget_id, plan__household=request.household,
    )
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in {"review", "approve", "changes", "reject"}:
            raise Http404
        lines = list(budget.lines.all())
        if action == "changes":
            with transaction.atomic():
                budget.lines.update(
                    approved_amount=ZERO,
                    status=PersonalBudgetLine.Status.PENDING,
                )
                budget.status = PersonalBudget.Status.CHANGES
                budget.reviewer_comment = request.POST.get("reviewer_comment", "").strip()
                budget.reviewed_by = request.user
                budget.reviewed_at = timezone.now()
                budget.save(update_fields=[
                    "status", "reviewer_comment", "reviewed_by", "reviewed_at"
                ])
            messages.success(request, "El presupuesto quedó abierto para ajustes.")
            return redirect(f"{redirect('family_finance:dashboard').url}?plan={budget.plan_id}")
        valid = True
        decisions = {}
        for line in lines:
            decision = "reject" if action == "reject" else request.POST.get(
                f"decision_{line.pk}", "approve"
            )
            if decision not in {"approve", "reject"}:
                valid = False
                messages.error(request, f"Selecciona una decisión para {line.description}.")
                continue
            amount = ZERO
            if decision == "approve":
                amount = _money(request.POST.get(f"approved_{line.pk}", "0"))
                if amount is None:
                    valid = False
                    messages.error(request, f"Valor inválido para {line.description}.")
            decisions[line.pk] = (decision, amount)
        if valid:
            with transaction.atomic():
                approved_any = False
                for line in lines:
                    decision, amount = decisions[line.pk]
                    line.status = (
                        PersonalBudgetLine.Status.APPROVED
                        if decision == "approve" else PersonalBudgetLine.Status.REJECTED
                    )
                    line.approved_amount = amount if decision == "approve" else ZERO
                    line.save(update_fields=["status", "approved_amount"])
                    approved_any = approved_any or decision == "approve"
                budget.status = (
                    PersonalBudget.Status.APPROVED
                    if approved_any else PersonalBudget.Status.REJECTED
                )
                budget.reviewer_comment = request.POST.get("reviewer_comment", "").strip()
                budget.reviewed_by = request.user
                budget.reviewed_at = timezone.now()
                budget.save(update_fields=[
                    "status", "reviewer_comment", "reviewed_by", "reviewed_at"
                ])
            messages.success(request, "Decisiones por línea registradas.")
            return redirect(f"{redirect('family_finance:dashboard').url}?plan={budget.plan_id}")
    return render(request, "family_finance/review_budget.html", {"budget": budget})


def _refresh_budget_status(budget, user):
    lines = budget.lines.all()
    if lines.filter(status=PersonalBudgetLine.Status.APPROVED).exists():
        status = PersonalBudget.Status.APPROVED
    elif lines.exists() and not lines.filter(status=PersonalBudgetLine.Status.PENDING).exists():
        status = PersonalBudget.Status.REJECTED
    else:
        status = PersonalBudget.Status.SUBMITTED
    budget.status = status
    budget.reviewed_by = user
    budget.reviewed_at = timezone.now()
    budget.save(update_fields=["status", "reviewed_by", "reviewed_at"])


@owner_required
def budget_line_review(request, line_id):
    if request.method != "POST":
        raise Http404
    line = get_object_or_404(
        PersonalBudgetLine.objects.select_related("budget__plan"),
        pk=line_id, budget__plan__household=request.household,
    )
    action = request.POST.get("action")
    if action not in {"approve", "reject"}:
        raise Http404
    amount = ZERO if action == "reject" else _money(request.POST.get("approved_amount", "0"))
    if amount is None:
        messages.error(request, "El valor aprobado no es válido.")
        return redirect("family_finance:budget_review", budget_id=line.budget_id)
    line.status = PersonalBudgetLine.Status.APPROVED if action == "approve" else PersonalBudgetLine.Status.REJECTED
    line.approved_amount = amount
    line.save(update_fields=["status", "approved_amount"])
    _refresh_budget_status(line.budget, request.user)
    messages.success(request, f"{line.description}: {'aprobado' if action == 'approve' else 'rechazado'}.")
    return redirect("family_finance:budget_review", budget_id=line.budget_id)


@owner_required
def budget_reopen(request, budget_id):
    if request.method != "POST":
        raise Http404
    budget = get_object_or_404(
        PersonalBudget.objects.prefetch_related("lines"),
        pk=budget_id, plan__household=request.household,
    )
    if budget.status in {PersonalBudget.Status.REJECTED, PersonalBudget.Status.APPROVED}:
        with transaction.atomic():
            budget.lines.update(
                approved_amount=ZERO,
                status=PersonalBudgetLine.Status.PENDING,
            )
            budget.status = PersonalBudget.Status.CHANGES
            budget.reviewer_comment = ""
            budget.reviewed_by = request.user
            budget.reviewed_at = timezone.now()
            budget.save(update_fields=[
                "status", "reviewer_comment", "reviewed_by", "reviewed_at"
            ])
        messages.success(request, f"El presupuesto de {budget.member.display_name} quedó abierto para editar.")
    else:
        messages.info(request, "Ese presupuesto ya se encuentra disponible para editar.")
    return redirect(f"{redirect('family_finance:dashboard').url}?plan={budget.plan_id}")


@family_member_required
def expense_list(request):
    plan = _selected_plan(request)
    qs = Expense.objects.none()
    if plan:
        qs = plan.expenses.select_related("member", "category")
        if not request.family_membership.can_manage:
            qs = qs.filter(member=request.family_membership)
    return render(request, "family_finance/expense_list.html", {"plan": plan, "expenses": qs})


def _category_limit(plan, membership, category):
    if membership.can_approve:
        return None
    extras = plan.extra_requests.filter(
        member=membership, category=category, status=ExtraRequest.Status.APPROVED
    ).aggregate(total=Sum("approved_amount"))["total"] or ZERO
    personal_lines = PersonalBudgetLine.objects.filter(
        budget__plan=plan, budget__member=membership,
        budget__status=PersonalBudget.Status.APPROVED, category=category,
    )
    if membership.role == FamilyMembership.Role.CHILD or personal_lines.exists():
        base = personal_lines.aggregate(total=Sum("approved_amount"))["total"] or ZERO
        spent = plan.expenses.filter(member=membership, category=category).aggregate(
            total=Sum("amount")
        )["total"] or ZERO
    else:
        base = plan.allocations.filter(category=category).aggregate(
            total=Sum("planned_amount")
        )["total"] or ZERO
        spent = plan.expenses.filter(category=category).aggregate(
            total=Sum("amount")
        )["total"] or ZERO
    return base + extras - spent


@family_member_required
def expense_create(request):
    membership = request.family_membership
    plan = _selected_plan(request)
    if not plan:
        messages.error(request, "Primero debe existir un presupuesto mensual.")
        return redirect("family_finance:dashboard")
    form = ExpenseForm(
        request.POST or None, request.FILES or None,
        household=request.household,
        child=membership.role != FamilyMembership.Role.OWNER,
    )
    if request.method == "POST" and form.is_valid():
        limit = _category_limit(plan, membership, form.cleaned_data["category"])
        if limit is not None and form.cleaned_data["amount"] > limit:
            messages.error(
                request,
                "Este gasto supera lo aprobado. Envía una solicitud adicional antes de registrarlo.",
            )
        else:
            expense = form.save(commit=False)
            expense.plan, expense.member = plan, membership
            expense.save()
            messages.success(request, "Gasto registrado. El saldo se actualizó.")
            return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Registrar gasto", "submit_label": "Guardar gasto",
        "helper": "Si supera el presupuesto aprobado, primero debes solicitar autorización.",
    })


@family_member_required
def extra_request_create(request):
    plan = _selected_plan(request)
    if not plan:
        return redirect("family_finance:dashboard")
    form = ExtraRequestForm(
        request.POST or None, household=request.household,
        child=request.family_membership.role != FamilyMembership.Role.OWNER,
    )
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.plan, item.member = plan, request.family_membership
        item.save()
        messages.success(request, "Solicitud enviada para aprobación.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Solicitar gasto adicional",
        "submit_label": "Enviar solicitud",
    })


@owner_required
def extra_request_review(request, request_id):
    item = get_object_or_404(
        ExtraRequest.objects.select_related("member", "category", "plan"),
        pk=request_id, plan__household=request.household,
    )
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in {"approve", "reject"}:
            raise Http404
        amount = _money(request.POST.get("approved_amount", "0"))
        if action == "approve" and amount is None:
            messages.error(request, "Indica un valor aprobado válido.")
        else:
            item.status = ExtraRequest.Status.APPROVED if action == "approve" else ExtraRequest.Status.REJECTED
            item.approved_amount = amount if action == "approve" else ZERO
            item.reviewer_comment = request.POST.get("reviewer_comment", "").strip()
            item.reviewed_by = request.user
            item.reviewed_at = timezone.now()
            item.save()
            messages.success(request, "Solicitud revisada.")
            return redirect(f"{redirect('family_finance:dashboard').url}?plan={item.plan_id}")
    return render(request, "family_finance/review_request.html", {"item": item})


@manager_required
def wallet_transfer_create(request):
    plan = _selected_plan(request)
    if not plan:
        return redirect("family_finance:dashboard")
    form = WalletTransferForm(request.POST or None, household=request.household)
    if request.method == "POST" and form.is_valid():
        transfer = form.save(commit=False)
        transfer.plan, transfer.created_by = plan, request.user
        if transfer.method == WalletTransfer.Method.CASH:
            transfer.status = WalletTransfer.Status.CONFIRMED
            transfer.confirmed_at = timezone.now()
        transfer.save()
        if transfer.method == WalletTransfer.Method.CASH:
            messages.success(request, "Entrega de efectivo registrada.")
        else:
            messages.success(request, "Transferencia a Nequi registrada; el hijo puede confirmarla.")
        return redirect(f"{redirect('family_finance:dashboard').url}?plan={plan.pk}")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Registrar dinero entregado",
        "submit_label": "Registrar entrega",
        "helper": "Seleccione Nequi o efectivo. No se guardan claves ni códigos de Nequi.",
    })


@family_member_required
def wallet_transfer_confirm(request, transfer_id):
    if request.method != "POST":
        raise Http404
    transfer = get_object_or_404(
        WalletTransfer, pk=transfer_id, member=request.family_membership,
        plan__household=request.household,
    )
    if request.family_membership.role != FamilyMembership.Role.CHILD:
        raise Http404
    transfer.status = WalletTransfer.Status.CONFIRMED
    transfer.confirmed_at = timezone.now()
    transfer.save(update_fields=["status", "confirmed_at"])
    messages.success(request, "Confirmaste que recibiste el dinero.")
    return redirect("family_finance:dashboard")


@manager_required
def savings_goal_create(request):
    form = SavingsGoalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        goal = form.save(commit=False)
        goal.household = request.household
        goal.save()
        messages.success(request, "Meta familiar creada.")
        return redirect("family_finance:dashboard")
    return render(request, "family_finance/form.html", {
        "form": form, "title": "Nueva meta de ahorro", "submit_label": "Crear meta"
    })
