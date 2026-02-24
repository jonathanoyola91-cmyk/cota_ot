from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from django.conf import settings
import requests

from historial.services import archive_if_not_exists
from workorders.models import WorkOrder


FINAL_STATE = WorkOrder.Status.TERMINADA


# =========================
# Helper interno Telegram
# =========================

def send_telegram(chat_id: str, text: str) -> bool:
    token = getattr(settings, "TG_BOT_TOKEN", "")
    enabled = getattr(settings, "TG_ENABLED", True)

    if not enabled or not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception:
        # No romper producción si Telegram falla
        return False


def get_user_chat_id(user) -> str:
    if not user:
        return ""
    profile = getattr(user, "profile", None)
    return getattr(profile, "telegram_chat_id", "") if profile else ""


# =========================
# CAPTURAR ESTADO ANTERIOR
# =========================

@receiver(pre_save, sender=WorkOrder)
def workorder_capture_previous_state(sender, instance: WorkOrder, **kwargs):
    if not instance.pk:
        instance._prev_estado = None
        instance._prev_asignado_a_id = None
        return

    old = (
        WorkOrder.objects
        .filter(pk=instance.pk)
        .values("estado", "asignado_a_id")
        .first()
    )

    instance._prev_estado = old["estado"] if old else None
    instance._prev_asignado_a_id = old["asignado_a_id"] if old else None


# =========================
# POST SAVE
# =========================

@receiver(post_save, sender=WorkOrder)
def workorder_post_save_logic(sender, instance: WorkOrder, created: bool, **kwargs):

    prev_estado = getattr(instance, "_prev_estado", None)

    # =========================================================
    # 1️⃣ MANTENER TU LÓGICA ACTUAL DE ARCHIVADO
    # =========================================================
    if prev_estado != FINAL_STATE and instance.estado == FINAL_STATE:
        archive_if_not_exists(
            area="WORKORDERS",
            instance=instance,
            title=str(instance),
        )

    # =========================================================
    # 2️⃣ NUEVA LÓGICA: NOTIFICAR CAMBIO DE ESTADO AL ASIGNADO
    # =========================================================

    # No notificar en creación inicial
    if created:
        return

    # Solo si hubo cambio real de estado
    if prev_estado == instance.estado:
        return

    # Debe haber usuario asignado
    if not instance.asignado_a_id:
        return

    chat_id = get_user_chat_id(instance.asignado_a)
    if not chat_id:
        return

    mensaje = (
        f"🔔 Actualización de OT\n\n"
        f"OT #{instance.numero}\n"
        f"Título: {instance.titulo}\n"
        f"Estado: {prev_estado or '—'} → {instance.estado}\n"
        f"Prioridad: {instance.prioridad}"
    )

    send_telegram(chat_id, mensaje)