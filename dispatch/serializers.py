from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import Driver, EmergencyRequest, EmergencyRequestCandidate, Hospital, PatientProfile, User


class RegisterPatientSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "password", "first_name", "last_name", "email"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(**validated_data, role=User.Role.PATIENT)
        user.set_password(password)
        user.save()
        PatientProfile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        login = attrs["username"]
        password = attrs["password"]

        # Allow login via email OR username
        if "@" in login:
            user_obj = User.objects.filter(email__iexact=login).only("username").first()
            if user_obj:
                login = user_obj.username

        user = authenticate(username=login, password=password)
        if not user:
            raise serializers.ValidationError("Incorrect email or password.")
        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "name",
            "email",
            "role",
            "phone_number",
        ]

    def get_phone_number(self, obj):
        profile = getattr(obj, "patient_profile", None)
        return getattr(profile, "phone", None)

    def get_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name or obj.username


class UserProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # Accept either phone_number or phone (frontend may send either)
        if "phone" in attrs and "phone_number" not in attrs:
            attrs["phone_number"] = attrs["phone"]
        return attrs


class HospitalCreateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    email = serializers.EmailField()
    address = serializers.CharField(required=False, allow_blank=True, default="")
    phone_number = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    bed_count = serializers.IntegerField(required=False, min_value=0, default=0)
    icu_count = serializers.IntegerField(required=False, min_value=0, default=0)

    def validate(self, attrs):
        if attrs.get("phone_number") not in (None, "") and attrs.get("phone") in (None, ""):
            attrs["phone"] = attrs["phone_number"]
        return attrs

    def create(self, validated_data):
        email = validated_data["email"].strip()
        username = (validated_data.get("username") or "").strip() or email
        user = User.objects.create_user(
            username=username,
            email=email,
            role=User.Role.HOSPITAL,
        )
        user.set_password(validated_data["password"])
        user.save()
        address = validated_data.get("address") or ""
        phone = validated_data.get("phone") or validated_data.get("phone_number") or ""
        hospital = Hospital.objects.create(
            user=user,
            name=validated_data["name"],
            address=address,
            phone=phone,
            latitude=validated_data["latitude"],
            longitude=validated_data["longitude"],
            bed_count=int(validated_data.get("bed_count") or 0),
            icu_count=int(validated_data.get("icu_count") or 0),
        )
        return hospital


class PatientHospitalSerializer(serializers.ModelSerializer):
    distance_meters = serializers.SerializerMethodField()
    phone_number = serializers.CharField(source="phone", read_only=True)

    class Meta:
        model = Hospital
        fields = [
            "id",
            "name",
            "address",
            "phone_number",
            "latitude",
            "longitude",
            "bed_count",
            "icu_count",
            "distance_meters",
        ]

    def get_distance_meters(self, obj):
        return int(getattr(obj, "distance_meters", 0))


class HospitalPortalSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source="phone", read_only=True)

    class Meta:
        model = Hospital
        fields = [
            "id",
            "name",
            "address",
            "phone_number",
            "latitude",
            "longitude",
            "bed_count",
            "icu_count",
        ]


class HospitalPortalUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)
    bed_count = serializers.IntegerField(required=False, min_value=0)
    icu_count = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        if "phone" in attrs and "phone_number" not in attrs:
            attrs["phone_number"] = attrs["phone"]
        return attrs


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ["id", "name", "phone", "status", "current_latitude", "current_longitude", "hospital", "user"]
        read_only_fields = ["hospital"]


class EmergencyRequestCreateSerializer(serializers.ModelSerializer):
    target_hospital_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = EmergencyRequest
        fields = [
            "id",
            "emergency_type",
            "patient_latitude",
            "patient_longitude",
            "status",
            "created_at",
            "target_hospital_id",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def create(self, validated_data):
        from .services import create_hospital_candidates

        target_hospital_id = validated_data.pop("target_hospital_id", None)
        patient = validated_data.pop("patient")
        emergency_request = EmergencyRequest.objects.create(patient=patient, **validated_data)
        create_hospital_candidates(emergency_request, target_hospital_id=target_hospital_id)
        return emergency_request


class EmergencyCandidateSerializer(serializers.ModelSerializer):
    hospital_name = serializers.CharField(source="hospital.name", read_only=True)

    class Meta:
        model = EmergencyRequestCandidate
        fields = ["id", "hospital", "hospital_name", "rank", "decision", "distance_meters", "responded_at"]


class EmergencyRequestSerializer(serializers.ModelSerializer):
    candidates = EmergencyCandidateSerializer(many=True, read_only=True)
    assigned_driver = DriverSerializer(read_only=True)
    accepted_hospital_name = serializers.CharField(source="accepted_hospital.name", read_only=True)

    class Meta:
        model = EmergencyRequest
        fields = [
            "id",
            "patient",
            "emergency_type",
            "patient_latitude",
            "patient_longitude",
            "status",
            "active_rank",
            "failure_reason",
            "accepted_hospital",
            "accepted_hospital_name",
            "assigned_driver",
            "candidates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
