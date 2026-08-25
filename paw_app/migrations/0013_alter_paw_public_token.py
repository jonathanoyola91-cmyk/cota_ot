import uuid

from django.db import migrations, models


def generar_tokens_unicos(apps, schema_editor):
    Paw = apps.get_model("paw_app", "Paw")

    for paw in Paw.objects.all().iterator():
        paw.public_token = uuid.uuid4()
        paw.save(update_fields=["public_token"])


class Migration(migrations.Migration):

    dependencies = [
        (
            "paw_app",
            "0012_paw_public_token_paw_seguimiento_publico_activo_and_more",
        ),
    ]

    operations = [

        # Primero asignamos un UUID diferente
        # a cada PAW que ya existe.
        migrations.RunPython(
            generar_tokens_unicos,
            migrations.RunPython.noop,
        ),

        # Después sí aplicamos UNIQUE.
        migrations.AlterField(
            model_name="paw",
            name="public_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                verbose_name="Token público de seguimiento",
            ),
        ),
    ]