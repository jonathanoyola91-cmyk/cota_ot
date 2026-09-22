from django.db import migrations


def add_household_subscriptions_category(apps, schema_editor):
    Household = apps.get_model("family_finance", "Household")
    Category = apps.get_model("family_finance", "Category")
    for household in Household.objects.all():
        Category.objects.get_or_create(
            household=household,
            name="Hogar y suscripciones",
            kind="FIXED",
            defaults={"color": "#7c3aed", "active": True},
        )


class Migration(migrations.Migration):
    dependencies = [("family_finance", "0001_initial")]

    operations = [migrations.RunPython(add_household_subscriptions_category, migrations.RunPython.noop)]
