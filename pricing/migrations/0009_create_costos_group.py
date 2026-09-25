from django.db import migrations

GROUP_NAME = 'COSTOS Y PRICING'

def create_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=GROUP_NAME)

def remove_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('pricing', '0008_cif_config'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [migrations.RunPython(create_group, remove_group)]
