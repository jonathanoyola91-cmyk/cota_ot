from django.urls import path

from . import views


app_name = "family_finance"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("configurar/", views.setup_household, name="setup"),
    path("familia/agregar/", views.member_create, name="member_create"),
    path("mes/nuevo/", views.plan_create, name="plan_create"),
    path("mes/<int:plan_id>/ingreso/", views.income_create, name="income_create"),
    path("ingreso/<int:item_id>/editar/", views.income_edit, name="income_edit"),
    path("mes/<int:plan_id>/gasto-fijo/", views.fixed_expense_create, name="fixed_create"),
    path("gasto-fijo/<int:item_id>/editar/", views.fixed_expense_edit, name="fixed_edit"),
    path("mes/<int:plan_id>/meta-gasto/", views.allocation_create, name="allocation_create"),
    path("meta-gasto/<int:item_id>/editar/", views.allocation_edit, name="allocation_edit"),
    path("mi-presupuesto/", views.my_budget, name="my_budget"),
    path("mi-presupuesto/linea/", views.budget_line_create, name="budget_line_create"),
    path("mi-presupuesto/linea/<int:line_id>/eliminar/", views.budget_line_delete, name="budget_line_delete"),
    path("mi-presupuesto/enviar/", views.budget_submit, name="budget_submit"),
    path("presupuesto/<int:budget_id>/revisar/", views.budget_review, name="budget_review"),
    path("gastos/", views.expense_list, name="expense_list"),
    path("gastos/nuevo/", views.expense_create, name="expense_create"),
    path("solicitudes/nueva/", views.extra_request_create, name="request_create"),
    path("solicitudes/<int:request_id>/revisar/", views.extra_request_review, name="request_review"),
    path("nequi/transferir/", views.wallet_transfer_create, name="wallet_transfer_create"),
    path("nequi/<int:transfer_id>/confirmar/", views.wallet_transfer_confirm, name="wallet_transfer_confirm"),
    path("metas/nueva/", views.savings_goal_create, name="goal_create"),
]
