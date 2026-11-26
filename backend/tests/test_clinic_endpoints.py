from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Appointment, Doctor, Slot


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _booked_slot_ids(db: Session) -> set[int]:
    return set(db.scalars(select(Appointment.slot_id).where(Appointment.status.in_(["booked"]))).all())


# --- auth -------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/doctors", "/api/doctors/1/slots", "/api/guides", "/api/guides/opening-hours", "/api/dashboard"])
def test_clinic_endpoints_require_login(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthenticated"


# --- doctors ----------------------------------------------------------------

def test_doctors_lists_six_with_clinic(login) -> None:
    doctors = login("patient").get("/api/doctors").json()

    assert len(doctors) == 6
    assert set(doctors[0]) == {"id", "name", "specialty", "bio", "clinic", "next_available"}
    assert doctors[0]["clinic"] == {"id": doctors[0]["clinic"]["id"], "name": "Terra Family Clinic"}


# --- slots ------------------------------------------------------------------

def test_slots_default_window_is_future_free_and_ordered(login, db: Session) -> None:
    doctor_id = db.scalar(select(Doctor.id).order_by(Doctor.id).limit(1))
    now = datetime.now(UTC)

    slots = login("patient").get(f"/api/doctors/{doctor_id}/slots").json()

    assert slots
    assert set(slots[0]) == {"id", "starts_at", "ends_at"}
    starts = [_parse(slot["starts_at"]) for slot in slots]
    assert starts == sorted(starts)
    assert all(now < start < now + timedelta(days=14) for start in starts)
    assert not {slot["id"] for slot in slots} & _booked_slot_ids(db)


def test_slots_hides_booked_slot_of_maya(login, db: Session) -> None:
    maya = login("patient")
    booked = maya.get("/api/appointments?status=booked").json()[0]
    doctor_id = booked["doctor"]["id"]

    slot_ids = {slot["id"] for slot in maya.get(f"/api/doctors/{doctor_id}/slots?days=30").json()}

    assert booked["slot"]["id"] not in slot_ids


def test_slots_respects_days_window(login) -> None:
    client = login("patient")
    doctor_id = client.get("/api/doctors").json()[0]["id"]
    now = datetime.now(UTC)

    slots = client.get(f"/api/doctors/{doctor_id}/slots?days=3").json()

    assert all(_parse(slot["starts_at"]) < now + timedelta(days=3) for slot in slots)


@pytest.mark.parametrize("days", [0, 31, "abc"])
def test_slots_days_out_of_range_is_422(login, days) -> None:
    response = login("patient").get(f"/api/doctors/1/slots?days={days}")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


def test_slots_unknown_doctor_is_404(login) -> None:
    response = login("patient").get("/api/doctors/999999/slots")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "doctor_not_found"


# --- guides -----------------------------------------------------------------

def test_guides_list_returns_seeded_slug_and_title(login) -> None:
    from app.seed import GUIDES
    guides = login("patient").get("/api/guides").json()

    # The library also includes operator-published RAG guides when an index exists.
    assert {(slug, title) for slug, title, _ in GUIDES} <= {(g["slug"], g["title"]) for g in guides}
    assert len({g["slug"] for g in guides}) == len(guides)
    assert all(set(guide) == {"slug", "title"} for guide in guides)


def test_guide_detail_returns_body(login) -> None:
    response = login("patient").get("/api/guides/opening-hours")

    assert response.status_code == 200
    assert set(response.json()) == {"slug", "title", "body"}
    assert response.json()["slug"] == "opening-hours"


def test_unknown_guide_slug_is_404(login) -> None:
    response = login("patient").get("/api/guides/no-such-guide")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "guide_not_found"


# --- dashboard --------------------------------------------------------------

def test_dashboard_for_maya_counts_and_next_appointment(login, db: Session) -> None:
    maya = login("patient")

    body = maya.get("/api/dashboard").json()

    assert set(body) == {"user", "next_appointment", "counts", "recent_activity", "staff_summary"}
    assert body["staff_summary"] is None
    assert body["user"] == {"id": body["user"]["id"], "name": "Maya Patel", "email": "maya.patel@terra.example", "role": "patient"}
    assert body["counts"] == {"upcoming": 2, "completed": 2, "cancelled": 1}
    earliest_booked = maya.get("/api/appointments?status=booked").json()[0]
    assert body["next_appointment"]["id"] == earliest_booked["id"]


def test_dashboard_recent_activity_is_capped_and_newest_first(login) -> None:
    body = login("patient").get("/api/dashboard").json()

    activity = body["recent_activity"]
    assert 0 < len(activity) <= 5
    assert {item["kind"] for item in activity} <= {"booked", "cancelled", "completed"}
    stamps = [_parse(item["at"]) for item in activity]
    assert stamps == sorted(stamps, reverse=True)
    for item in activity:
        assert set(item) == {"kind", "text", "at"}


def test_dashboard_booked_activity_text_names_doctor_and_time(login) -> None:
    activity = login("patient").get("/api/dashboard").json()["recent_activity"]

    booked = [item for item in activity if item["kind"] == "booked"]
    assert booked
    assert booked[0]["text"].startswith("Booked Dr. ")
    assert " on " in booked[0]["text"]


def test_dashboard_for_staff_counts_all_patients(login, db: Session) -> None:
    now = datetime.now(UTC)
    upcoming = db.scalar(
        select(func.count())
        .select_from(Appointment)
        .join(Slot, Appointment.slot_id == Slot.id)
        .where(Appointment.status.in_(["booked"]), Slot.starts_at > now)
    )
    completed = db.scalar(select(func.count()).select_from(Appointment).where(Appointment.status.in_(["completed"])))

    body = login("receptionist").get("/api/dashboard").json()

    assert body["counts"]["upcoming"] == upcoming
    assert body["counts"]["completed"] == completed
    earliest_booked = login("receptionist").get("/api/appointments?status=booked").json()[0]
    assert body["next_appointment"]["id"] == earliest_booked["id"]


def test_dashboard_next_appointment_is_null_when_nothing_upcoming(login, db: Session) -> None:
    client = login("patient")
    maya_id = client.get("/api/auth/me").json()["id"]
    db.execute(Appointment.__table__.update().where(Appointment.patient_id == maya_id).values(status="completed"))
    db.commit()

    body = client.get("/api/dashboard").json()

    assert body["next_appointment"] is None
    assert body["counts"]["upcoming"] == 0
