from django.apps import AppConfig

class PresupuestoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "presupuesto"

    def ready(self):
        import presupuesto.signals  # noqa