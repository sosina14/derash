from django.db import migrations
from django.contrib.auth.hashers import make_password


def seed_demo_accounts(apps, schema_editor):
    User = apps.get_model("dispatch", "User")
    Hospital = apps.get_model("dispatch", "Hospital")
    Driver = apps.get_model("dispatch", "Driver")

    # 1) Ensure admin has the requested email/password
    #    (password may already be set by 0002; keep it as admin123)
    admin_user, created = User.objects.get_or_create(
        username="admin",
        defaults={
            "email": "admin@gmail.com",
            "role": "ADMIN",
            "is_staff": True,
            "is_superuser": True,
        },
    )
    if not created:
        changed = False
        if admin_user.email != "admin@gmail.com":
            admin_user.email = "admin@gmail.com"
            changed = True
        if admin_user.role != "ADMIN":
            admin_user.role = "ADMIN"
            changed = True
        if not admin_user.is_staff:
            admin_user.is_staff = True
            changed = True
        if not admin_user.is_superuser:
            admin_user.is_superuser = True
            changed = True
        if changed:
            admin_user.save()

    # Always ensure the password is admin123 (migration-safe)
    admin_user.password = make_password("admin123")
    admin_user.save(update_fields=["password"])

    # 2) Seed a demo hospital account (loginable via email)
    demo_hospital_email = "hospital.demo@gmail.com"
    demo_hospital_password = "hosp1234"

    hospital_user = User.objects.filter(email__iexact=demo_hospital_email).first()
    if not hospital_user:
        hospital_user = User.objects.create(
            username="hospital_demo",
            email=demo_hospital_email,
            role="HOSPITAL",
        )
        hospital_user.password = make_password(demo_hospital_password)
        hospital_user.save(update_fields=["password"])
    else:
        if hospital_user.role != "HOSPITAL":
            hospital_user.role = "HOSPITAL"
            hospital_user.save(update_fields=["role"])
        hospital_user.password = make_password(demo_hospital_password)
        hospital_user.save(update_fields=["password"])

    Hospital.objects.get_or_create(
        user=hospital_user,
        defaults={
            "name": "Demo Hospital (Addis Ababa)",
            "latitude": 9.03,
            "longitude": 38.74,
        },
    )

    # 3) Seed a demo driver account (loginable via email)
    #    Driver is linked to a hospital AND a DRIVER user (new field from 0003).
    demo_driver_email = "driver.demo@gmail.com"
    demo_driver_password = "driver1234"

    driver_user = User.objects.filter(email__iexact=demo_driver_email).first()
    if not driver_user:
        driver_user = User.objects.create(
            username="driver_demo",
            email=demo_driver_email,
            role="DRIVER",
        )
        driver_user.password = make_password(demo_driver_password)
        driver_user.save(update_fields=["password"])
    else:
        if driver_user.role != "DRIVER":
            driver_user.role = "DRIVER"
            driver_user.save(update_fields=["role"])
        driver_user.password = make_password(demo_driver_password)
        driver_user.save(update_fields=["password"])

    hospital = Hospital.objects.filter(user=hospital_user).first()
    if hospital:
        Driver.objects.get_or_create(
            user=driver_user,
            defaults={
                "hospital": hospital,
                "name": "Abebe Kebede",
                "phone": "+251911223344",
                "status": "AVAILABLE",
                "current_latitude": hospital.latitude,
                "current_longitude": hospital.longitude,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("dispatch", "0003_driver_user_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(seed_demo_accounts, migrations.RunPython.noop),
    ]

