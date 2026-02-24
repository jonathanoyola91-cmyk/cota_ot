from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telegram_chat_id = models.BigIntegerField(
        blank=True,
        null=True,
        unique=True
    )

    def __str__(self):
        return self.user.username