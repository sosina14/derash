from django.db import models, transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Driver, EmergencyRequest, EmergencyRequestCandidate, Hospital, User
from .permissions import IsAdminRole, IsHospital, IsPatient
from .serializers import (
    DriverSerializer,
    EmergencyRequestCreateSerializer,
    EmergencyRequestSerializer,
    HospitalCreateSerializer,
    HospitalPortalSerializer,
    HospitalPortalUpdateSerializer,
    LoginSerializer,
    PatientHospitalSerializer,
    RegisterPatientSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
)
from .services import haversine_distance_meters, mark_candidate_rejected


class PatientRegisterView(generics.CreateAPIView):
    serializer_class = RegisterPatientSerializer
    permission_classes = [AllowAny]


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        display_name = user.get_full_name().strip() or user.username
        payload = {
            "token": token.key,
            "role": user.role,
            "user_id": user.id,
            "name": display_name,
            "email": user.email or "",
        }
        driver_profile = getattr(user, "driver_profile", None)
        if driver_profile is not None:
            payload["driver_id"] = driver_profile.id
        return Response(payload)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)


class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    # Frontend calls POST auth/profile/update/
    def post(self, request):
        serializer = UserProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        if "email" in data:
            user.email = data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])

        phone = data.get("phone_number")
        # Only patients have a patient_profile by default; if missing, ignore silently
        patient_profile = getattr(user, "patient_profile", None)
        if patient_profile is not None and phone is not None:
            patient_profile.phone = phone
            patient_profile.save(update_fields=["phone"])

        return Response(UserProfileSerializer(user).data)


class CreateHospitalView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        hospitals = Hospital.objects.all().order_by("id")
        return Response(HospitalPortalSerializer(hospitals, many=True).data)

    def post(self, request):
        serializer = HospitalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hospital = serializer.save()
        return Response(HospitalPortalSerializer(hospital).data, status=status.HTTP_201_CREATED)


class AdminHospitalDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_object(self, hospital_id: int):
        return Hospital.objects.filter(id=hospital_id).first()

    def patch(self, request, hospital_id: int):
        hospital = self.get_object(hospital_id)
        if not hospital:
            return Response({"detail": "Hospital not found."}, status=404)

        serializer = HospitalPortalUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "name" in data and data["name"]:
            hospital.name = data["name"]
        if "address" in data:
            hospital.address = data["address"] or ""
        phone = data.get("phone_number") or data.get("phone")
        if phone is not None:
            hospital.phone = phone or ""
        if "latitude" in data:
            hospital.latitude = data["latitude"]
        if "longitude" in data:
            hospital.longitude = data["longitude"]
        if "bed_count" in data:
            hospital.bed_count = max(0, int(data["bed_count"]))
        if "icu_count" in data:
            hospital.icu_count = max(0, int(data["icu_count"]))

        hospital.save(
            update_fields=[
                "name",
                "address",
                "phone",
                "latitude",
                "longitude",
                "bed_count",
                "icu_count",
            ]
        )
        return Response(HospitalPortalSerializer(hospital).data)

    def delete(self, request, hospital_id: int):
        hospital = self.get_object(hospital_id)
        if not hospital:
            return Response({"detail": "Hospital not found."}, status=404)

        # Also delete the associated user to avoid orphaned logins.
        user = hospital.user
        hospital.delete()
        if user:
            user.delete()
        return Response(status=204)


class PatientHospitalListView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        lat_raw = request.query_params.get("lat")
        lng_raw = request.query_params.get("lng")

        hospitals = list(Hospital.objects.all().order_by("id"))

        # If no coordinates are provided, return a stable list with mock distances.
        if not lat_raw or not lng_raw:
            for idx, h in enumerate(hospitals):
                h.distance_meters = (idx + 1) * 1000
            return Response(PatientHospitalSerializer(hospitals, many=True).data)

        try:
            lat = float(lat_raw)
            lng = float(lng_raw)
        except (TypeError, ValueError):
            for idx, h in enumerate(hospitals):
                h.distance_meters = (idx + 1) * 1000
            return Response(PatientHospitalSerializer(hospitals, many=True).data)

        for h in hospitals:
            h.distance_meters = haversine_distance_meters(lat, lng, h.latitude, h.longitude)
        hospitals.sort(key=lambda h: h.distance_meters)
        return Response(PatientHospitalSerializer(hospitals, many=True).data)


class HospitalPortalProfileView(APIView):
    permission_classes = [IsAuthenticated, IsHospital]

    def get(self, request):
        hospital = request.user.hospital_profile
        return Response(HospitalPortalSerializer(hospital).data)


class HospitalPortalProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsHospital]

    def post(self, request):
        serializer = HospitalPortalUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        hospital = request.user.hospital_profile

        if "name" in data and data["name"]:
            hospital.name = data["name"]
        if "address" in data:
            hospital.address = data["address"] or ""
        phone = data.get("phone_number") or data.get("phone")
        if phone is not None:
            hospital.phone = phone or ""
        if "latitude" in data:
            hospital.latitude = data["latitude"]
        if "longitude" in data:
            hospital.longitude = data["longitude"]
        if "bed_count" in data:
            hospital.bed_count = max(0, int(data["bed_count"]))
        if "icu_count" in data:
            hospital.icu_count = max(0, int(data["icu_count"]))

        hospital.save(
            update_fields=[
                "name",
                "address",
                "phone",
                "latitude",
                "longitude",
                "bed_count",
                "icu_count",
            ]
        )
        return Response(HospitalPortalSerializer(hospital).data)


class DriverListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsHospital]

    def get(self, request):
        drivers = Driver.objects.filter(hospital=request.user.hospital_profile).order_by("id")
        return Response(DriverSerializer(drivers, many=True).data)

    def post(self, request):
        data = request.data.copy()

        # Optional: create a loginable DRIVER user for this driver
        email = data.pop("email", None)
        password = data.pop("password", None)
        # Use email as username when provided so drivers can sign in with email like patients.
        username = data.pop("username", None)
        if isinstance(email, str) and email.strip():
            username = (username or "").strip() or email.strip()

        serializer = DriverSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        driver_user = None
        if email and password and username:
            driver_user = User.objects.create_user(username=username, email=email, role=User.Role.DRIVER)
            driver_user.set_password(password)
            driver_user.save()

        driver = serializer.save(hospital=request.user.hospital_profile, user=driver_user)
        return Response(DriverSerializer(driver).data, status=status.HTTP_201_CREATED)


class DriverLocationUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsHospital]

    def patch(self, request, driver_id):
        driver = Driver.objects.filter(id=driver_id, hospital=request.user.hospital_profile).first()
        if not driver:
            return Response({"detail": "Driver not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = DriverSerializer(driver, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DriverSelfLocationUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        driver_profile = getattr(request.user, "driver_profile", None)
        if not driver_profile:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
        serializer = DriverSerializer(driver_profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PatientRequestLocationUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def patch(self, request, request_id):
        emergency_request = EmergencyRequest.objects.filter(
            id=request_id,
            patient=request.user
        ).first()
        if not emergency_request:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        patient_latitude = request.data.get("patient_latitude")
        patient_longitude = request.data.get("patient_longitude")
        if patient_latitude is not None:
            emergency_request.patient_latitude = float(patient_latitude)
        if patient_longitude is not None:
            emergency_request.patient_longitude = float(patient_longitude)
        emergency_request.save(update_fields=["patient_latitude", "patient_longitude", "updated_at"])
        return Response(EmergencyRequestSerializer(emergency_request).data)


class EmergencyRequestCreateView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    @transaction.atomic
    def post(self, request):
        serializer = EmergencyRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emergency_request = serializer.save(patient=request.user)
        return Response(EmergencyRequestSerializer(emergency_request).data, status=status.HTTP_201_CREATED)


class PatientEmergencyRequestListView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        items = EmergencyRequest.objects.filter(patient=request.user).order_by("-created_at")
        return Response(EmergencyRequestSerializer(items, many=True).data)


class HospitalIncomingRequestListView(APIView):
    permission_classes = [IsAuthenticated, IsHospital]

    def get(self, request):
        candidates = EmergencyRequestCandidate.objects.filter(
            hospital=request.user.hospital_profile,
            decision=EmergencyRequestCandidate.Decision.PENDING,
            rank=models.F("request__active_rank"),
            request__status=EmergencyRequest.Status.PENDING,
        ).select_related("request")
        data = [EmergencyRequestSerializer(c.request).data for c in candidates]
        return Response(data)


class HospitalDecisionView(APIView):
    permission_classes = [IsAuthenticated, IsHospital]

    @transaction.atomic
    def post(self, request, request_id):
        decision = request.data.get("decision")
        driver_id = request.data.get("driver_id")
        emergency_request = EmergencyRequest.objects.select_for_update().filter(id=request_id).first()
        if not emergency_request:
            return Response({"detail": "Request not found."}, status=status.HTTP_404_NOT_FOUND)
        if emergency_request.status != EmergencyRequest.Status.PENDING:
            return Response({"detail": "Request is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        candidate = EmergencyRequestCandidate.objects.select_for_update().filter(
            request=emergency_request,
            hospital=request.user.hospital_profile,
            rank=emergency_request.active_rank,
            decision=EmergencyRequestCandidate.Decision.PENDING,
        ).first()
        if not candidate:
            return Response({"detail": "This request is not currently routed to your hospital."}, status=400)

        if decision == "REJECT":
            mark_candidate_rejected(candidate)
            return Response(EmergencyRequestSerializer(emergency_request).data)

        if decision != "ACCEPT":
            return Response({"detail": "decision must be ACCEPT or REJECT"}, status=400)

        if not driver_id:
            emergency_request.status = EmergencyRequest.Status.FAILED
            emergency_request.failure_reason = "No driver available at acceptance"
            emergency_request.save(update_fields=["status", "failure_reason", "updated_at"])
            candidate.decision = EmergencyRequestCandidate.Decision.ACCEPTED
            candidate.responded_at = timezone.now()
            candidate.save(update_fields=["decision", "responded_at"])
            return Response(EmergencyRequestSerializer(emergency_request).data)

        driver = Driver.objects.select_for_update().filter(
            id=driver_id,
            hospital=request.user.hospital_profile,
            status=Driver.Status.AVAILABLE,
        ).first()
        if not driver:
            emergency_request.status = EmergencyRequest.Status.FAILED
            emergency_request.failure_reason = "No driver available at acceptance"
            emergency_request.save(update_fields=["status", "failure_reason", "updated_at"])
            return Response(EmergencyRequestSerializer(emergency_request).data)

        candidate.decision = EmergencyRequestCandidate.Decision.ACCEPTED
        candidate.responded_at = timezone.now()
        candidate.save(update_fields=["decision", "responded_at"])

        emergency_request.accepted_hospital = request.user.hospital_profile
        emergency_request.assigned_driver = driver
        emergency_request.status = EmergencyRequest.Status.ASSIGNED
        emergency_request.save(update_fields=["accepted_hospital", "assigned_driver", "status", "updated_at"])

        driver.status = Driver.Status.UNAVAILABLE
        if driver.current_latitude is None:
            driver.current_latitude = request.user.hospital_profile.latitude
            driver.current_longitude = request.user.hospital_profile.longitude
        driver.save(update_fields=["status", "current_latitude", "current_longitude"])
        return Response(EmergencyRequestSerializer(emergency_request).data)


class EmergencyTrackingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id):
        emergency_request = EmergencyRequest.objects.filter(id=request_id).first()
        if not emergency_request:
            return Response({"detail": "Request not found."}, status=404)

        is_patient_owner = request.user.role == User.Role.PATIENT and emergency_request.patient_id == request.user.id
        is_hospital_owner = (
            request.user.role == User.Role.HOSPITAL
            and emergency_request.accepted_hospital_id == request.user.hospital_profile.id
        )
        is_assigned_driver = (
            request.user.role == User.Role.DRIVER
            and emergency_request.assigned_driver is not None
            and hasattr(request.user, 'driver_profile')
            and emergency_request.assigned_driver_id == request.user.driver_profile.id
        )
        if not (is_patient_owner or is_hospital_owner or is_assigned_driver):
            return Response({"detail": "Forbidden."}, status=403)

        driver = emergency_request.assigned_driver
        if not driver:
            return Response({"detail": "Driver not assigned yet."}, status=400)

        start_lat = emergency_request.accepted_hospital.latitude
        start_lon = emergency_request.accepted_hospital.longitude
        return Response(
            {
                "request_id": emergency_request.id,
                "driver_id": driver.id,
                "driver_status": driver.status,
                "driver_location": {
                    "latitude": driver.current_latitude,
                    "longitude": driver.current_longitude,
                },
                "route": {
                    "start": {"latitude": start_lat, "longitude": start_lon},
                    "end": {
                        "latitude": emergency_request.patient_latitude,
                        "longitude": emergency_request.patient_longitude,
                    },
                },
            }
        )
from django.shortcuts import render

# Create your views here.
