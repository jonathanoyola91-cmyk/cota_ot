from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Historial(models.Model):
    area = models.CharField(max_length=50, db_index=True)

    # Referencia genérica al objeto original (WorkOrder, PAW, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    closed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # título descriptivo para mostrar en listados
    title = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-closed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="uniq_historial_content_object",
            )
        ]

    def __str__(self):
        return f"[{self.area}] {self.title or f'#{self.object_id}'}"