from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "PATIENT", "Patient"
        HOSPITAL = "HOSPITAL", "Hospital"
        ADMIN = "ADMIN", "Admin"
        DRIVER = "DRIVER", "Driver"

    role = models.CharField(max_length=20, choices=Role.choices)


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="patient_profile")
    phone = models.CharField(max_length=25, blank=True)

    def __str__(self):
        return f"PatientProfile({self.user.username})"


class Hospital(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="hospital_profile")
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])
    bed_count = models.PositiveIntegerField(default=0)
    icu_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Driver(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="drivers")
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="driver_profile")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=25, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    current_latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)], null=True, blank=True)
    current_longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)], null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.hospital.name})"


class EmergencyRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        ASSIGNED = "ASSIGNED", "Assigned"
        FAILED = "FAILED", "Failed"

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="emergency_requests")
    emergency_type = models.CharField(max_length=100, blank=True)
    patient_latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    patient_longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    accepted_hospital = models.ForeignKey(
        Hospital,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_requests",
    )
    assigned_driver = models.OneToOneField(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_request",
    )
    active_rank = models.PositiveSmallIntegerField(default=1)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"EmergencyRequest#{self.pk} ({self.status})"


class EmergencyRequestCandidate(models.Model):
    class Decision(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        SKIPPED = "SKIPPED", "Skipped"

    request = models.ForeignKey(EmergencyRequest, on_delete=models.CASCADE, related_name="candidates")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="incoming_candidates")
    rank = models.PositiveSmallIntegerField()
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.PENDING)
    distance_meters = models.PositiveIntegerField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["rank"]
        unique_together = ("request", "hospital")

    def __str__(self):
        return f"Req#{self.request_id} -> {self.hospital.name} ({self.rank})"

# Create your models here.
