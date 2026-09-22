from django.contrib import admin

from .models import (
    BudgetAllocation, Category, Debt, DebtPayment, Expense, ExtraRequest, FamilyMembership,
    FixedExpense, Household, Income, MonthlyPlan, PersonalBudget,
    PersonalBudgetLine, SavingsGoal, WalletTransfer,
)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "currency", "created_at")


@admin.register(FamilyMembership)
class FamilyMembershipAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "household", "role", "active")
    list_filter = ("household", "role", "active")


admin.site.register(Category)
admin.site.register(MonthlyPlan)
admin.site.register(Income)
admin.site.register(FixedExpense)
admin.site.register(Debt)
admin.site.register(DebtPayment)
admin.site.register(BudgetAllocation)
admin.site.register(PersonalBudget)
admin.site.register(PersonalBudgetLine)
admin.site.register(ExtraRequest)
admin.site.register(Expense)
admin.site.register(WalletTransfer)
admin.site.register(SavingsGoal)
