from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import (
    BudgetAllocation,
    Category,
    Expense,
    ExtraRequest,
    FamilyMembership,
    MonthlyPlan,
    PersonalBudget,
    ZERO,
)


def money_sum(queryset, field):
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def plan_totals(plan):
    expected_income = money_sum(plan.incomes.all(), "expected_amount")
    received_income = money_sum(plan.incomes.all(), "received_amount")
    fixed_budget = money_sum(plan.fixed_expenses.all(), "budgeted_amount")
    fixed_paid = money_sum(plan.fixed_expenses.all(), "paid_amount")
    variable_budget = money_sum(plan.allocations.all(), "planned_amount")
    personal_approved = money_sum(
        plan.personal_budgets.filter(status=PersonalBudget.Status.APPROVED).values("lines"),
        "lines__approved_amount",
    )
    variable_spent = money_sum(plan.expenses.all(), "amount")
    committed = fixed_budget + plan.savings_target + variable_budget + personal_approved
    return {
        "expected_income": expected_income,
        "received_income": received_income,
        "fixed_budget": fixed_budget,
        "fixed_paid": fixed_paid,
        "variable_budget": variable_budget,
        "personal_approved": personal_approved,
        "spent": variable_spent,
        "committed": committed,
        "available_to_assign": received_income - fixed_budget - plan.savings_target,
        "projected_balance": received_income - fixed_paid - variable_spent - plan.savings_target,
        "fixed_ratio": round((fixed_budget / received_income) * 100) if received_income else 0,
    }


def category_rows(plan, visible_to_family=True):
    today = date.today()
    days_in_month = monthrange(plan.year, plan.month)[1]
    elapsed = max(1, min(today.day, days_in_month)) if (today.year, today.month) == (plan.year, plan.month) else days_in_month
    rows = []
    for allocation in plan.allocations.select_related("category"):
        spent = money_sum(plan.expenses.filter(category=allocation.category), "amount")
        approved_extra = money_sum(
            plan.extra_requests.filter(
                category=allocation.category, status=ExtraRequest.Status.APPROVED
            ),
            "approved_amount",
        )
        limit = allocation.planned_amount + approved_extra
        remaining = limit - spent
        percent = round((spent / limit) * 100) if limit else 0
        projected = (spent / Decimal(elapsed)) * Decimal(days_in_month) if spent else ZERO
        if percent >= 100:
            level = "red"
            message = f"Meta superada por ${abs(remaining):,.0f}"
        elif percent >= 90:
            level = "red"
            message = "Presupuesto casi agotado"
        elif percent >= 75:
            level = "yellow"
            message = "Conviene reducir el ritmo de gasto"
        else:
            level = "green"
            message = f"Quedan ${remaining:,.0f}"
        rows.append({
            "allocation": allocation,
            "spent": spent,
            "limit": limit,
            "remaining": remaining,
            "percent": min(100, max(0, percent)),
            "raw_percent": percent,
            "projected": projected,
            "level": level,
            "message": message,
        })
    return rows


def spending_ranking(plan, limit=6):
    """Actual spending by category, including fixed payments and daily expenses."""
    totals = {}
    for row in plan.expenses.values("category__name", "category__color").annotate(
        amount=Sum("amount")
    ):
        key = (row["category__name"], row["category__color"])
        totals[key] = totals.get(key, ZERO) + (row["amount"] or ZERO)
    for row in plan.fixed_expenses.values("category__name", "category__color").annotate(
        amount=Sum("paid_amount")
    ):
        key = (row["category__name"], row["category__color"])
        totals[key] = totals.get(key, ZERO) + (row["amount"] or ZERO)

    total_spent = sum(totals.values(), ZERO)
    rows = [
        {
            "name": name,
            "color": color,
            "amount": amount,
            "percent": round((amount / total_spent) * 100) if total_spent else 0,
        }
        for (name, color), amount in totals.items()
    ]
    return sorted(rows, key=lambda row: row["amount"], reverse=True)[:limit]


def smart_recommendations(plan):
    """Short, concrete recommendations from the family's own registered data."""
    recommendations = []
    totals = plan_totals(plan)
    rows = category_rows(plan)

    exceeded = [row for row in rows if row["raw_percent"] >= 100]
    caution = [row for row in rows if 75 <= row["raw_percent"] < 100]
    if exceeded:
        row = max(exceeded, key=lambda item: item["raw_percent"])
        recommendations.append({
            "level": "red",
            "title": f"Detener gasto en {row['allocation'].category.name}",
            "message": (
                f"Ya se superó la meta por ${abs(row['remaining']):,.0f}. "
                "No autoricen nuevos gastos de esta categoría sin revisar el presupuesto."
            ),
        })
    elif caution:
        row = max(caution, key=lambda item: item["raw_percent"])
        recommendations.append({
            "level": "yellow",
            "title": f"Reducir el ritmo en {row['allocation'].category.name}",
            "message": (
                f"Ya usaron {row['raw_percent']}% de la meta. Quedan ${max(ZERO, row['remaining']):,.0f} "
                "para el resto del mes."
            ),
        })

    if totals["fixed_ratio"] >= 75:
        recommendations.append({
            "level": "red",
            "title": "Primero cubrir las obligaciones del hogar",
            "message": (
                f"Los gastos fijos representan {totals['fixed_ratio']}% del ingreso recibido. "
                "Aplacen compras no necesarias hasta pagar vivienda, colegio, servicios y deudas."
            ),
        })
    elif totals["fixed_ratio"] >= 60:
        recommendations.append({
            "level": "yellow",
            "title": "Cuidar las compras variables",
            "message": (
                f"Los gastos fijos ya usan {totals['fixed_ratio']}% del ingreso recibido. "
                "Revisen cada compra adicional antes de autorizarla."
            ),
        })

    ranking = spending_ranking(plan, limit=2)
    market = next((item for item in ranking if item["name"] == "Mercado"), None)
    food_out = next((item for item in ranking if item["name"] == "Comidas fuera"), None)
    if food_out and (not market or food_out["amount"] >= market["amount"]):
        recommendations.append({
            "level": "yellow",
            "title": "Priorizar mercado antes de comidas fuera",
            "message": (
                f"Comidas fuera suma ${food_out['amount']:,.0f}. Planeen el mercado y las comidas de la semana "
                "antes de destinar más dinero a salidas o domicilios."
            ),
        })

    if not recommendations:
        recommendations.append({
            "level": "green",
            "title": "Van bien por ahora",
            "message": (
                "No hay categorías en alerta. Mantengan el registro diario y revisen el tablero "
                "antes de una compra importante."
            ),
        })
    return recommendations[:3]


def personal_summary(plan, membership):
    budget = plan.personal_budgets.filter(member=membership).first()
    approved = budget.approved_total if budget and budget.status == PersonalBudget.Status.APPROVED else ZERO
    approved_extra = money_sum(
        plan.extra_requests.filter(member=membership, status=ExtraRequest.Status.APPROVED),
        "approved_amount",
    )
    spent = money_sum(plan.expenses.filter(member=membership), "amount")
    transferred = money_sum(plan.wallet_transfers.filter(member=membership), "amount")
    nequi_transferred = money_sum(
        plan.wallet_transfers.filter(member=membership, method="NEQUI"), "amount"
    )
    cash_received = money_sum(
        plan.wallet_transfers.filter(member=membership, method="CASH"), "amount"
    )
    nequi_spent = money_sum(
        plan.expenses.filter(member=membership, source=Expense.Source.NEQUI), "amount"
    )
    cash_spent = money_sum(
        plan.expenses.filter(member=membership, source=Expense.Source.CASH), "amount"
    )
    limit = approved + approved_extra
    return {
        "budget": budget,
        "approved": approved,
        "approved_extra": approved_extra,
        "limit": limit,
        "spent": spent,
        "remaining": limit - spent,
        "transferred": transferred,
        "nequi_transferred": nequi_transferred,
        "cash_received": cash_received,
        "pending_delivery": limit - transferred,
        "nequi_balance": nequi_transferred - nequi_spent,
        "cash_balance": cash_received - cash_spent,
        "percent": min(100, round((spent / limit) * 100)) if limit else 0,
    }


def seed_categories(household):
    defaults = [
        ("Arriendo o vivienda", Category.Kind.FIXED, "#475569"),
        ("Servicios públicos", Category.Kind.FIXED, "#0f766e"),
        ("Hogar y suscripciones", Category.Kind.FIXED, "#7c3aed"),
        ("Colegio", Category.Kind.FIXED, "#7c3aed"),
        ("Transporte escolar", Category.Kind.FIXED, "#2563eb"),
        ("Salud y seguros", Category.Kind.FIXED, "#0891b2"),
        ("Tarjetas de crédito", Category.Kind.DEBT, "#dc2626"),
        ("Otros créditos", Category.Kind.DEBT, "#b91c1c"),
        ("Mercado", Category.Kind.VARIABLE, "#16a34a"),
        ("Comidas fuera", Category.Kind.VARIABLE, "#ea580c"),
        ("Entretenimiento", Category.Kind.VARIABLE, "#9333ea"),
        ("Ropa y compras", Category.Kind.VARIABLE, "#db2777"),
        ("Transporte", Category.Kind.VARIABLE, "#0284c7"),
        ("Imprevistos", Category.Kind.VARIABLE, "#64748b"),
        ("Meriendas", Category.Kind.CHILD, "#f59e0b"),
        ("Estudio", Category.Kind.CHILD, "#4f46e5"),
        ("Diversión", Category.Kind.CHILD, "#ec4899"),
        ("Compras personales", Category.Kind.CHILD, "#8b5cf6"),
        ("Ahorro personal", Category.Kind.CHILD, "#059669"),
    ]
    for name, kind, color in defaults:
        Category.objects.get_or_create(
            household=household, name=name, kind=kind, defaults={"color": color}
        )
