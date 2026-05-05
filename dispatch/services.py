import math
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.utils import timezone

from .models import EmergencyRequest, EmergencyRequestCandidate, Hospital


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    r = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return int(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def get_google_distances(patient_lat: float, patient_lon: float, hospitals: list[Hospital]) -> dict[int, int]:
    api_key = getattr(settings, "GOOGLE_DISTANCE_MATRIX_API_KEY", "")
    if not api_key:
        return {
            hospital.id: haversine_distance_meters(patient_lat, patient_lon, hospital.latitude, hospital.longitude)
            for hospital in hospitals
        }

    destinations = "|".join(f"{h.latitude},{h.longitude}" for h in hospitals)
    params = urllib.parse.urlencode(
        {
            "origins": f"{patient_lat},{patient_lon}",
            "destinations": destinations,
            "key": api_key,
        }
    )
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?{params}"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload: Any = response.read().decode("utf-8")
    import json

    data = json.loads(payload)
    elements = data["rows"][0]["elements"]
    distances = {}
    for idx, hospital in enumerate(hospitals):
        element = elements[idx]
        if element.get("status") == "OK":
            distances[hospital.id] = int(element["distance"]["value"])
        else:
            distances[hospital.id] = haversine_distance_meters(
                patient_lat, patient_lon, hospital.latitude, hospital.longitude
            )
    return distances


def create_hospital_candidates(
    emergency_request: EmergencyRequest,
    target_hospital_id: int | None = None,
) -> None:
    """
    Builds routing candidates for an emergency request.
    If ``target_hospital_id`` is set (patient chose a hospital), only that hospital is notified.
    Otherwise all hospitals are ranked nearest → farthest.
    """

    hospitals = list(Hospital.objects.all())
    if target_hospital_id is not None:
        hospital = next((h for h in hospitals if h.id == int(target_hospital_id)), None)
        if not hospital:
            emergency_request.status = EmergencyRequest.Status.FAILED
            emergency_request.failure_reason = "Selected hospital was not found"
            emergency_request.save(update_fields=["status", "failure_reason", "updated_at"])
            return
        distance = haversine_distance_meters(
            emergency_request.patient_latitude,
            emergency_request.patient_longitude,
            hospital.latitude,
            hospital.longitude,
        )
        EmergencyRequestCandidate.objects.create(
            request=emergency_request,
            hospital=hospital,
            rank=1,
            distance_meters=distance,
        )
        emergency_request.active_rank = 1
        emergency_request.save(update_fields=["active_rank", "updated_at"])
        return

    if not hospitals:
        emergency_request.status = EmergencyRequest.Status.FAILED
        emergency_request.failure_reason = "No hospitals available"
        emergency_request.save(update_fields=["status", "failure_reason", "updated_at"])
        return

    distances = get_google_distances(
        emergency_request.patient_latitude,
        emergency_request.patient_longitude,
        hospitals,
    )
    ranked = sorted(hospitals, key=lambda h: distances[h.id])
    if not ranked:
        emergency_request.status = EmergencyRequest.Status.FAILED
        emergency_request.failure_reason = "No hospitals available"
        emergency_request.save(update_fields=["status", "failure_reason", "updated_at"])
        return

    for rank, hospital in enumerate(ranked, start=1):
        EmergencyRequestCandidate.objects.create(
            request=emergency_request,
            hospital=hospital,
            rank=rank,
            distance_meters=distances[hospital.id],
        )
    emergency_request.active_rank = 1
    emergency_request.save(update_fields=["active_rank", "updated_at"])


def advance_to_next_hospital(emergency_request: EmergencyRequest) -> None:
    next_candidate = emergency_request.candidates.filter(
        rank__gt=emergency_request.active_rank, decision=EmergencyRequestCandidate.Decision.PENDING
    ).order_by("rank").first()
    if not next_candidate:
        emergency_request.status = EmergencyRequest.Status.FAILED
        emergency_request.failure_reason = "All hospitals rejected"
        emergency_request.save(update_fields=["status", "failure_reason", "updated_at"])
        return
    emergency_request.active_rank = next_candidate.rank
    emergency_request.save(update_fields=["active_rank", "updated_at"])


def mark_candidate_rejected(candidate: EmergencyRequestCandidate) -> None:
    candidate.decision = EmergencyRequestCandidate.Decision.REJECTED
    candidate.responded_at = timezone.now()
    candidate.save(update_fields=["decision", "responded_at"])
    advance_to_next_hospital(candidate.request)
