from django.contrib.auth.models import User
from accounts.models import Profile

def start(update, context):
    chat_id = update.effective_chat.id
    telegram_username = update.effective_user.username

    # 🔹 Opción simple: buscar por username
    profile = Profile.objects.filter(
        user__username=telegram_username
    ).first()

    if not profile:
        update.message.reply_text(
            "❌ No encontré tu usuario en el sistema.\n"
            "Por favor regístrate primero en la plataforma."
        )
        return

    # Guardar chat_id
    profile.telegram_chat_id = chat_id
    profile.save()

    update.message.reply_text(
        "✅ Tu cuenta fue vinculada correctamente con Telegram."
    )