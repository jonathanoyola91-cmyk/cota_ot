from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission

@receiver(post_migrate)
def create_entrega_taller_group(sender, **kwargs):
    if sender.name != "inventario":
        return

    group, _ = Group.objects.get_or_create(name="ENTREGA TALLER")

    perms = Permission.objects.filter(
        content_type__app_label="inventario",
        codename__in=[
            "add_workshopdelivery",
            "change_workshopdelivery",
            "view_workshopdelivery",
            "add_workshopdeliveryline",
            "view_workshopdeliveryline",
        ],
    )
    group.permissions.add(*perms)
