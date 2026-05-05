from django.db import migrations


def seed_admin(apps, schema_editor):
    User = apps.get_model("dispatch", "User")
    if User.objects.filter(username="admin").exists():
        return
    User.objects.create_superuser(
        username="admin",
        password="admin123",
        role="ADMIN",
        is_staff=True,
        is_superuser=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("dispatch", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_admin, migrations.RunPython.noop),
    ]
