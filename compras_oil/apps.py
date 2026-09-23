from django.apps import AppConfig


class ComprasOilConfig(AppConfig):
    name = 'compras_oil'

    def ready(self):
        from . import signals  # noqa: F401
