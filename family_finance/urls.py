from django.urls import path

from . import views


app_name = "family_finance"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("instalar/", views.install_access, name="install_access"),
    path("configurar/", views.setup_household, name="setup"),
    path("prueba/nueva-familia/", views.trial_family_create, name="trial_family_create"),
    path("familia/agregar/", views.member_create, name="member_create"),
    path("familia/vincular-usuario/", views.member_link_existing, name="member_link_existing"),
    path("mes/nuevo/", views.plan_create, name="plan_create"),
    path("mes/<int:plan_id>/copiar-siguiente/", views.plan_copy_next_month, name="plan_copy_next_month"),
    path("mes/<int:plan_id>/ingreso/", views.income_create, name="income_create"),
    path("ingreso/<int:item_id>/editar/", views.income_edit, name="income_edit"),
    path("mes/<int:plan_id>/gasto-fijo/", views.fixed_expense_create, name="fixed_create"),
    path("gasto-fijo/<int:item_id>/editar/", views.fixed_expense_edit, name="fixed_edit"),
    path("gasto-fijo/<int:item_id>/eliminar/", views.fixed_expense_delete, name="fixed_delete"),
    path("deudas/nueva/", views.debt_create, name="debt_create"),
    path("deudas/<int:debt_id>/pago/", views.debt_payment_create, name="debt_payment_create"),
    path("deudas/<int:debt_id>/editar/", views.debt_edit, name="debt_edit"),
    path("mes/<int:plan_id>/meta-gasto/", views.allocation_create, name="allocation_create"),
    path("meta-gasto/<int:item_id>/editar/", views.allocation_edit, name="allocation_edit"),
    path("mi-presupuesto/", views.my_budget, name="my_budget"),
    path("mi-presupuesto/linea/", views.budget_line_create, name="budget_line_create"),
    path("mi-presupuesto/linea/<int:line_id>/eliminar/", views.budget_line_delete, name="budget_line_delete"),
    path("mi-presupuesto/enviar/", views.budget_submit, name="budget_submit"),
    path("presupuesto/<int:budget_id>/revisar/", views.budget_review, name="budget_review"),
    path("presupuesto/linea/<int:line_id>/decidir/", views.budget_line_review, name="budget_line_review"),
    path("presupuesto/<int:budget_id>/reabrir/", views.budget_reopen, name="budget_reopen"),
    path("gastos/", views.expense_list, name="expense_list"),
    path("gastos/nuevo/", views.expense_create, name="expense_create"),
    path("solicitudes/nueva/", views.extra_request_create, name="request_create"),
    path("solicitudes/<int:request_id>/revisar/", views.extra_request_review, name="request_review"),
    path("nequi/transferir/", views.wallet_transfer_create, name="wallet_transfer_create"),
    path("nequi/<int:transfer_id>/confirmar/", views.wallet_transfer_confirm, name="wallet_transfer_confirm"),
    path("metas/nueva/", views.savings_goal_create, name="goal_create"),
]
