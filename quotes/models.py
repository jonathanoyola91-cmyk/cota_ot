# quotes/models.py
from django.db import models


class Cliente(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    nit = models.CharField(max_length=30, blank=True)
    ciudad = models.CharField(max_length=80, blank=True)
    contacto = models.CharField(max_length=120, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    correo = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]

    def save(self, *args, **kwargs):
        if self.nombre:
            self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Quotation(models.Model):
    class Estado(models.TextChoices):
        ADJUDICADA = "ADJUDICADA", "Adjudicada"
        EVALUACION = "EVALUACION", "Evaluación"
        CERRADA = "CERRADA", "Cerrada"

    class Empresa(models.TextChoices):
        IMPETUS = "IMPETUS", "Impetus"
        OIL_GAS = "OIL_GAS", "Oil & Gas"

    numero_cotizacion = models.CharField(
        "Número de cotización",
        max_length=50,
        unique=True
    )

    nombre_cotizacion = models.CharField(
        "Nombre de cotización",
        max_length=150
    )

    # Campo histórico para no romper PAW ni reportes actuales
    cliente = models.CharField(max_length=120)

    # Nuevo cliente maestro
    cliente_registrado = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cotizaciones"
    )

    campo = models.CharField(max_length=120, blank=True)
    fecha_cotizacion = models.DateField(null=True, blank=True)

    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.EVALUACION
    )

    empresa = models.CharField(
        max_length=12,
        choices=Empresa.choices,
        default=Empresa.IMPETUS
    )

    valor = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        default=0
    )

    observaciones = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.cliente_registrado:
            self.cliente = self.cliente_registrado.nombre
        super().save(*args, **kwargs)

    def __str__(self):
        return f"COT {self.numero_cotizacion} - {self.cliente}"