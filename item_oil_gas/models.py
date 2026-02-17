from django.db import models

class Item(models.Model):
    codigo = models.CharField("Código", max_length=30, unique=True)
    descripcion = models.TextField("Descripción")
    unidad_medida = models.CharField("Unidad Medida", max_length=20, blank=True, null=True)
    clasificacion = models.CharField("Clasificación", max_length=30, blank=True, null=True)
    grupo_inventario = models.CharField("Grupo Inventario", max_length=255, blank=True, null=True)

    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Item Oil & Gas"
        verbose_name_plural = "Items Oil & Gas"

    def __str__(self):
        return f"{self.codigo} - {self.descripcion[:60]}"