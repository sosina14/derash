from django.core.management.base import BaseCommand
from django.db import transaction

from dispatch.models import Driver, Hospital, User


class Command(BaseCommand):
    help = "Seed demo accounts (admin, demo hospital, demo driver). Safe to re-run."

    @transaction.atomic
    def handle(self, *args, **options):
        # Admin
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@gmail.com",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if admin.email != "admin@gmail.com":
            admin.email = "admin@gmail.com"
        admin.role = User.Role.ADMIN
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("admin123")
        admin.save()

        # Demo hospital user + hospital profile
        hospital_email = "hospital.demo@gmail.com"
        hospital_password = "hosp1234"

        hospital_user, created = User.objects.get_or_create(
            email=hospital_email,
            defaults={
                "username": "hospital_demo",
                "role": User.Role.HOSPITAL,
            },
        )
        if not created:
            hospital_user.role = User.Role.HOSPITAL
        if not hospital_user.username:
            hospital_user.username = "hospital_demo"
        hospital_user.set_password(hospital_password)
        hospital_user.save()

        hospital, _ = Hospital.objects.get_or_create(
            user=hospital_user,
            defaults={
                "name": "Demo Hospital (Addis Ababa)",
                "latitude": 9.03,
                "longitude": 38.74,
            },
        )

        # Demo driver user + driver profile
        driver_email = "driver.demo@gmail.com"
        driver_password = "driver1234"

        driver_user, created = User.objects.get_or_create(
            email=driver_email,
            defaults={
                "username": "driver_demo",
                "role": User.Role.DRIVER,
            },
        )
        if not created:
            driver_user.role = User.Role.DRIVER
        if not driver_user.username:
            driver_user.username = "driver_demo"
        driver_user.set_password(driver_password)
        driver_user.save()

        Driver.objects.get_or_create(
            user=driver_user,
            defaults={
                "hospital": hospital,
                "name": "Abebe Kebede",
                "phone": "+251911223344",
                "status": Driver.Status.AVAILABLE,
                "current_latitude": hospital.latitude,
                "current_longitude": hospital.longitude,
            },
        )

        self.stdout.write(self.style.SUCCESS("Seeded demo accounts."))
        self.stdout.write("Admin: admin@gmail.com / admin123")
        self.stdout.write("Hospital: hospital.demo@gmail.com / hosp1234")
        self.stdout.write("Driver: driver.demo@gmail.com / driver1234")

