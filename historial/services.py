from django.contrib.contenttypes.models import ContentType
from historial.models import Historial


def archive_if_not_exists(*, area: str, instance, title: str = ""):
    ct = ContentType.objects.get_for_model(instance.__class__)
    Historial.objects.get_or_create(
        area=area,
        content_type=ct,
        object_id=instance.pk,
        defaults={"title": title or str(instance)},
    )