from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    BudgetAllocation, Category, Debt, DebtPayment, Expense, ExtraRequest, FamilyMembership,
    Household, MonthlyPlan, PersonalBudget, PersonalBudgetLine, WalletTransfer,
)
from .services import seed_categories, smart_recommendations, spending_ranking


class FamilyBaseTest(TestCase):
    def setUp(self):
        self.owner_user = User.objects.create_user("padre", password="test12345", is_superuser=True, is_staff=True)
        self.spouse_user = User.objects.create_user("esposa", password="test12345")
        self.child_user = User.objects.create_user("hijo", password="test12345")
        self.other_child_user = User.objects.create_user("hija", password="test12345")
        self.employee = User.objects.create_user("empleado", password="test12345")
        self.household = Household.objects.create(name="Familia Prueba", owner=self.owner_user)
        self.owner = FamilyMembership.objects.create(
            household=self.household, user=self.owner_user, display_name="Papá",
            role=FamilyMembership.Role.OWNER,
        )
        self.spouse = FamilyMembership.objects.create(
            household=self.household, user=self.spouse_user, display_name="Mamá",
            role=FamilyMembership.Role.ADMIN,
        )
        self.child = FamilyMembership.objects.create(
            household=self.household, user=self.child_user, display_name="Juan",
            role=FamilyMembership.Role.CHILD,
        )
        self.other_child = FamilyMembership.objects.create(
            household=self.household, user=self.other_child_user, display_name="Ana",
            role=FamilyMembership.Role.CHILD,
        )
        seed_categories(self.household)
        self.assertTrue(self.household.categories.filter(
            name="Hogar y suscripciones", kind=Category.Kind.FIXED
        ).exists())
        self.food = self.household.categories.get(name="Comidas fuera", kind=Category.Kind.VARIABLE)
        self.fun = self.household.categories.get(name="Diversión", kind=Category.Kind.CHILD)
        self.plan = MonthlyPlan.objects.create(
            household=self.household, year=2026, month=9,
            savings_target=Decimal("500000"), created_by=self.owner_user,
        )


class AccessTests(FamilyBaseTest):
    def test_superuser_can_create_isolated_trial_family(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(reverse("family_finance:trial_family_create"), {
            "username": "padre_prueba", "first_name": "Carlos", "email": "carlos@example.com",
            "family_name": "Familia Cliente", "display_name": "Carlos",
            "password1": "clave-segura-123", "password2": "clave-segura-123",
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="padre_prueba")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        membership = user.family_membership
        self.assertEqual(membership.role, FamilyMembership.Role.OWNER)
        self.assertEqual(membership.household.name, "Familia Cliente")

    def test_regular_family_owner_cannot_create_trial_family(self):
        user = User.objects.create_user("otro_padre", password="test12345")
        other = Household.objects.create(name="Otra familia", owner=user)
        FamilyMembership.objects.create(
            household=other, user=user, display_name="Otro", role=FamilyMembership.Role.OWNER,
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("family_finance:trial_family_create")).status_code, 404)

    def test_regular_family_owner_cannot_open_existing_company_user_list(self):
        user = User.objects.create_user("otro_padre_2", password="test12345")
        other = Household.objects.create(name="Otra familia 2", owner=user)
        FamilyMembership.objects.create(
            household=other, user=user, display_name="Otro", role=FamilyMembership.Role.OWNER,
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("family_finance:member_link_existing")).status_code, 404)

    def test_business_messages_are_not_rendered_in_family_space(self):
        self.client.force_login(self.child_user)
        response = self.client.get("/pruebas/mensaje-empresa/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "MENSAJE INTERNO DE INVENTARIO")

    def test_family_messages_still_render(self):
        self.client.force_login(self.child_user)
        response = self.client.get(reverse("family_finance:plan_create"), follow=True)
        self.assertContains(response, "No tienes permiso para administrar")

    def test_owner_dashboard_renders_financial_summary(self):
        self.plan.incomes.create(
            name="Ingreso hogar", expected_amount=Decimal("10000000"),
            received_amount=Decimal("9000000"), created_by=self.owner_user,
        )
        BudgetAllocation.objects.create(
            plan=self.plan, category=self.food, planned_amount=Decimal("400000")
        )
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("family_finance:dashboard"), {"plan": self.plan.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresos recibidos")
        self.assertContains(response, "Comidas fuera")

    def test_spending_ranking_combines_daily_and_fixed_spending(self):
        fixed_category = self.household.categories.get(name="Servicios públicos")
        self.plan.fixed_expenses.create(
            category=fixed_category, name="Internet", budgeted_amount=Decimal("120000"),
            paid_amount=Decimal("120000"), created_by=self.owner_user,
        )
        Expense.objects.create(
            plan=self.plan, member=self.child, category=self.food,
            description="Almuerzo", amount=Decimal("200000"), date=date(2026, 9, 22),
            source=Expense.Source.CASH,
        )
        ranking = spending_ranking(self.plan)
        self.assertEqual(ranking[0]["name"], "Comidas fuera")
        self.assertEqual(ranking[0]["amount"], Decimal("200000"))

    def test_unpaid_fixed_expense_still_appears_as_monthly_commitment(self):
        fixed_category = self.household.categories.get(name="Servicios públicos")
        self.plan.fixed_expenses.create(
            category=fixed_category, name="Internet", budgeted_amount=Decimal("120000"),
            paid_amount=Decimal("0"), created_by=self.owner_user,
        )
        ranking = spending_ranking(self.plan)
        self.assertEqual(ranking[0]["name"], "Servicios públicos")
        self.assertEqual(ranking[0]["amount"], Decimal("120000"))

    def test_smart_recommendation_warns_when_food_outpaces_market(self):
        Expense.objects.create(
            plan=self.plan, member=self.child, category=self.food,
            description="Domicilios", amount=Decimal("250000"), date=date(2026, 9, 22),
            source=Expense.Source.CASH,
        )
        recommendations = smart_recommendations(self.plan)
        self.assertTrue(any(
            item["title"] == "Priorizar mercado antes de comidas fuera"
            for item in recommendations
        ))

    def test_spouse_dashboard_renders_but_does_not_offer_approval_button(self):
        request_item = ExtraRequest.objects.create(
            plan=self.plan, member=self.child, category=self.fun,
            description="Compra", requested_amount=Decimal("100000"), reason="Prueba",
        )
        self.client.force_login(self.spouse_user)
        response = self.client.get(reverse("family_finance:dashboard"), {"plan": self.plan.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pendiente del propietario")
        self.assertNotContains(response, reverse("family_finance:request_review", args=[request_item.pk]))

    def test_spouse_has_individual_budget_access_and_her_income_counts_for_home(self):
        self.plan.incomes.create(
            name="Ingreso de mamá", expected_amount=Decimal("2000000"),
            received_amount=Decimal("1800000"), created_by=self.spouse_user,
        )
        self.client.force_login(self.spouse_user)
        response = self.client.get(reverse("family_finance:dashboard"), {"plan": self.plan.pk})
        self.assertContains(response, "Mi presupuesto personal")
        self.assertContains(response, "Ingresos familiares")
        self.assertContains(response, "Ingreso de mamá")
        response = self.client.get(reverse("family_finance:my_budget"), {"plan": self.plan.pk})
        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_discover_family_module(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("family_finance:dashboard"))
        self.assertEqual(response.status_code, 404)

    def test_child_cannot_open_management_views(self):
        self.client.force_login(self.child_user)
        response = self.client.get(reverse("family_finance:plan_create"))
        self.assertRedirects(response, reverse("family_finance:dashboard"))
        response = self.client.get(reverse("family_finance:member_create"))
        self.assertRedirects(response, reverse("family_finance:dashboard"))

    def test_owner_can_link_existing_company_user_as_spouse(self):
        company_user = User.objects.create_user("gerencia", password="test12345")
        self.client.force_login(self.owner_user)
        response = self.client.post(reverse("family_finance:member_link_existing"), {
            "user": company_user.pk,
            "display_name": "Esposa",
            "role": FamilyMembership.Role.ADMIN,
        })
        self.assertRedirects(response, reverse("family_finance:dashboard"))
        self.assertTrue(FamilyMembership.objects.filter(
            household=self.household, user=company_user, role=FamilyMembership.Role.ADMIN
        ).exists())

    def test_spouse_cannot_approve_requests(self):
        item = ExtraRequest.objects.create(
            plan=self.plan, member=self.child, category=self.fun,
            description="Zapatos", requested_amount=Decimal("100000"), reason="Actividad",
        )
        self.client.force_login(self.spouse_user)
        response = self.client.post(
            reverse("family_finance:request_review", args=[item.pk]),
            {"action": "approve", "approved_amount": "100000"},
        )
        self.assertRedirects(response, reverse("family_finance:dashboard"))
        item.refresh_from_db()
        self.assertEqual(item.status, ExtraRequest.Status.PENDING)

    def test_child_dashboard_does_not_expose_parent_amounts(self):
        self.plan.incomes.create(
            name="Ingreso confidencial", expected_amount=Decimal("99999999"),
            received_amount=Decimal("99999999"), created_by=self.owner_user,
        )
        self.client.force_login(self.child_user)
        response = self.client.get(reverse("family_finance:dashboard"), {"plan": self.plan.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Ingreso confidencial")
        self.assertNotContains(response, "99,999,999")


class BudgetApprovalTests(FamilyBaseTest):
    def setUp(self):
        super().setUp()
        self.budget = PersonalBudget.objects.create(
            plan=self.plan, member=self.child, status=PersonalBudget.Status.SUBMITTED
        )
        self.line = PersonalBudgetLine.objects.create(
            budget=self.budget, category=self.fun, description="Salida al cine",
            requested_amount=Decimal("80000"), notes="Una salida",
        )

    def test_only_owner_approves_child_budget_and_can_adjust_value(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("family_finance:budget_review", args=[self.budget.pk]),
            {
                "action": "approve", f"approved_{self.line.pk}": "60000",
                "reviewer_comment": "Guarda una parte para ahorro",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.budget.refresh_from_db()
        self.line.refresh_from_db()
        self.assertEqual(self.budget.status, PersonalBudget.Status.APPROVED)
        self.assertEqual(self.line.approved_amount, Decimal("60000"))
        self.assertEqual(self.budget.reviewed_by, self.owner_user)

    def test_owner_can_approve_and_reject_different_lines(self):
        second_line = PersonalBudgetLine.objects.create(
            budget=self.budget, category=self.fun, description="Juego",
            requested_amount=Decimal("50000"),
        )
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("family_finance:budget_review", args=[self.budget.pk]),
            {
                "action": "review",
                f"decision_{self.line.pk}": "approve",
                f"approved_{self.line.pk}": "60000",
                f"decision_{second_line.pk}": "reject",
                f"approved_{second_line.pk}": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.line.refresh_from_db()
        second_line.refresh_from_db()
        self.assertEqual(self.line.status, PersonalBudgetLine.Status.APPROVED)
        self.assertEqual(second_line.status, PersonalBudgetLine.Status.REJECTED)
        self.assertEqual(second_line.approved_amount, Decimal("0"))

    def test_owner_can_approve_one_line_directly_before_full_submission(self):
        self.budget.status = PersonalBudget.Status.DRAFT
        self.budget.save(update_fields=["status"])
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse("family_finance:budget_line_review", args=[self.line.pk]),
            {"action": "approve", "approved_amount": "55000"},
        )
        self.assertEqual(response.status_code, 302)
        self.line.refresh_from_db()
        self.budget.refresh_from_db()
        self.assertEqual(self.line.status, PersonalBudgetLine.Status.APPROVED)
        self.assertEqual(self.line.approved_amount, Decimal("55000"))
        self.assertEqual(self.budget.status, PersonalBudget.Status.APPROVED)

    def test_child_cannot_spend_above_approved_category(self):
        self.budget.status = PersonalBudget.Status.APPROVED
        self.budget.save(update_fields=["status"])
        self.line.approved_amount = Decimal("60000")
        self.line.save(update_fields=["approved_amount"])
        self.client.force_login(self.child_user)
        response = self.client.post(reverse("family_finance:expense_create") + f"?plan={self.plan.pk}", {
            "category": self.fun.pk, "description": "Compra grande", "amount": "70000",
            "date": date(2026, 9, 22), "source": Expense.Source.NEQUI,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Expense.objects.exists())
        self.assertContains(response, "supera lo aprobado")

    def test_child_can_spend_within_approved_category(self):
        self.budget.status = PersonalBudget.Status.APPROVED
        self.budget.save(update_fields=["status"])
        self.line.approved_amount = Decimal("60000")
        self.line.save(update_fields=["approved_amount"])
        self.client.force_login(self.child_user)
        response = self.client.post(reverse("family_finance:expense_create") + f"?plan={self.plan.pk}", {
            "category": self.fun.pk, "description": "Cine", "amount": "40000",
            "date": date(2026, 9, 22), "source": Expense.Source.NEQUI,
        })
        self.assertEqual(response.status_code, 302)
        expense = Expense.objects.get()
        self.assertEqual(expense.member, self.child)
        self.assertEqual(expense.amount, Decimal("40000"))


class RequestAndWalletTests(FamilyBaseTest):
    def test_owner_can_partially_approve_extra_request(self):
        item = ExtraRequest.objects.create(
            plan=self.plan, member=self.child, category=self.fun,
            description="Camiseta", requested_amount=Decimal("90000"), reason="Evento",
        )
        self.client.force_login(self.owner_user)
        self.client.post(reverse("family_finance:request_review", args=[item.pk]), {
            "action": "approve", "approved_amount": "50000",
            "reviewer_comment": "Aprobación parcial",
        })
        item.refresh_from_db()
        self.assertEqual(item.status, ExtraRequest.Status.APPROVED)
        self.assertEqual(item.approved_amount, Decimal("50000"))

    def test_child_can_only_confirm_own_nequi_transfer(self):
        own = WalletTransfer.objects.create(
            plan=self.plan, member=self.child, amount=Decimal("60000"),
            date=date(2026, 9, 22), created_by=self.owner_user,
        )
        other = WalletTransfer.objects.create(
            plan=self.plan, member=self.other_child, amount=Decimal("60000"),
            date=date(2026, 9, 22), created_by=self.owner_user,
        )
        self.client.force_login(self.child_user)
        response = self.client.post(reverse("family_finance:wallet_transfer_confirm", args=[other.pk]))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse("family_finance:wallet_transfer_confirm", args=[own.pk]))
        self.assertEqual(response.status_code, 302)
        own.refresh_from_db()
        self.assertEqual(own.status, WalletTransfer.Status.CONFIRMED)

    def test_mother_can_register_cash_delivery_for_child(self):
        self.client.force_login(self.spouse_user)
        response = self.client.post(
            reverse("family_finance:wallet_transfer_create") + f"?plan={self.plan.pk}",
            {
                "member": self.child.pk,
                "amount": "30000",
                "method": WalletTransfer.Method.CASH,
                "date": date(2026, 9, 22),
                "note": "Merienda",
            },
        )
        self.assertEqual(response.status_code, 302)
        transfer = WalletTransfer.objects.get()
        self.assertEqual(transfer.method, WalletTransfer.Method.CASH)
        self.assertEqual(transfer.status, WalletTransfer.Status.CONFIRMED)

    def test_debt_payment_reduces_remaining_principal(self):
        category = self.household.categories.get(name="Tarjetas de crédito")
        debt = Debt.objects.create(
            household=self.household, category=category, name="Tarjeta Banco",
            opening_balance=Decimal("5000000"), monthly_payment=Decimal("450000"),
        )
        DebtPayment.objects.create(
            debt=debt, plan=self.plan, payment_amount=Decimal("450000"),
            principal_amount=Decimal("300000"), interest_amount=Decimal("150000"),
            payment_date=date(2026, 9, 22), created_by=self.owner_user,
        )
        self.assertEqual(debt.remaining_balance, Decimal("4700000"))

    def test_debt_estimates_interest_from_monthly_rate(self):
        category = self.household.categories.get(name="Tarjetas de crédito")
        debt = Debt.objects.create(
            household=self.household, category=category, name="Crédito",
            opening_balance=Decimal("1000000"), monthly_payment=Decimal("120000"),
            monthly_interest_rate=Decimal("2"),
        )
        self.assertEqual(debt.estimated_next_interest, Decimal("20000.00"))
        self.assertEqual(debt.estimated_next_principal, Decimal("100000.00"))

    def test_copy_month_carries_only_recurring_fixed_expenses(self):
        fixed = self.household.categories.get(name="Servicios públicos")
        self.plan.fixed_expenses.create(
            category=fixed, name="Internet", budgeted_amount=Decimal("100000"),
            recurring=True, created_by=self.owner_user,
        )
        self.plan.fixed_expenses.create(
            category=fixed, name="Reparación única", budgeted_amount=Decimal("50000"),
            recurring=False, created_by=self.owner_user,
        )
        self.client.force_login(self.owner_user)
        response = self.client.post(reverse("family_finance:plan_copy_next_month", args=[self.plan.pk]))
        self.assertEqual(response.status_code, 302)
        copied = MonthlyPlan.objects.get(household=self.household, year=2026, month=10)
        self.assertTrue(copied.fixed_expenses.filter(name="Internet").exists())
        self.assertFalse(copied.fixed_expenses.filter(name="Reparación única").exists())

    def test_child_login_goes_directly_to_family_module(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "hijo", "password": "test12345",
        })
        self.assertRedirects(response, reverse("family_finance:dashboard"))
