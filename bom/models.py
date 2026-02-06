from django.db import models
from django.utils import timezone


class BomTemplate(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class BomTemplateItem(models.Model):
    template = models.ForeignKey(BomTemplate, on_delete=models.CASCADE, related_name="items")

    plano = models.CharField(max_length=120, blank=True)
    codigo = models.CharField(max_length=80, blank=True)  # PARTE NUMERO
    descripcion = models.CharField(max_length=200)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad_estandar = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    observaciones = models.TextField(blank=True)

    class Meta:
        unique_together = ("template", "descripcion", "codigo", "plano")

    def __str__(self):
        return f"{self.template} - {self.descripcion}"


class Bom(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        SOLICITUD = "SOLICITUD", "Solicitud Inventario"

    workorder = models.OneToOneField(
        "workorders.WorkOrder",
        on_delete=models.PROTECT,
        related_name="bom",
    )
    template = models.ForeignKey(
        BomTemplate,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="boms",
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR)
    comentarios = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    solicitado_en = models.DateTimeField(null=True, blank=True)

    def marcar_solicitud(self):
        self.estado = self.Estado.SOLICITUD
        self.solicitado_en = timezone.now()
        self.save()

    def __str__(self):
        return f"BOM OT #{self.workorder.numero}"


class BomItem(models.Model):
    bom = models.ForeignKey(Bom, on_delete=models.CASCADE, related_name="items")

    plano = models.CharField(max_length=120, blank=True)
    codigo = models.CharField(max_length=80, blank=True)
    descripcion = models.CharField(max_length=200)
    unidad = models.CharField(max_length=20, blank=True)

    cantidad_estandar = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cantidad_solicitada = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.bom} - {self.descripcion}"
