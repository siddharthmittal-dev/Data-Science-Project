import threading
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Appointment, Doctor, Slot, User
from app.services.appointments import book
from app.services.errors import ServiceError


def _user_id(db: Session, name: str) -> int:
    return db.scalar(select(User.id).where(User.name == name))


def _free_future_slot(db: Session, doctor_name: str | None = None) -> Slot:
    now = datetime.now(UTC)
    booked = select(Appointment.slot_id).where(Appointment.status.in_(["booked"]))
    stmt = select(Slot).where(Slot.starts_at > now, Slot.id.not_in(booked))
    if doctor_name is not None:
        stmt = stmt.where(Slot.doctor_id.in_(select(Doctor.id).where(Doctor.name == doctor_name)))
    return db.scalars(stmt.order_by(Slot.starts_at, Slot.id)).first()


def _past_slot(db: Session) -> Slot:
    return db.scalars(select(Slot).where(Slot.starts_at < datetime.now(UTC)).order_by(Slot.starts_at)).first()


def _appointment_for(db: Session, patient_name: str, status: str) -> Appointment:
    return db.scalars(
        select(Appointment)
        .join(User, Appointment.patient_id == User.id)
        .where(User.name == patient_name, Appointment.status.in_([status]))
        .order_by(Appointment.id)
    ).first()


def _maya_booked(maya: TestClient) -> dict:
    return maya.get("/api/appointments?status=booked").json()[0]


# --- auth -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/appointments"),
        ("post", "/api/appointments"),
        ("post", "/api/appointments/1/reschedule"),
        ("post", "/api/appointments/1/cancel"),
    ],
)
def test_appointment_endpoints_require_login(client: TestClient, method: str, path: str) -> None:
    response = client.request(method.upper(), path, json={"slot_id": 1, "reason": "x", "patient_id": None})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthenticated"


# --- booking ----------------------------------------------------------------

def test_patient_books_free_slot_returns_201_with_item_shape(login, db: Session) -> None:
    maya = login("patient")
    slot = _free_future_slot(db, "Dr. Ananya Sharma")

    response = maya.post("/api/appointments", json={"slot_id": slot.id, "reason": "  Headache  "})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "status", "reason", "patient", "doctor", "slot", "legacy_schedule"}
    assert body["status"] == "booked"
    assert body["reason"] == "Headache"
    assert body["patient"]["name"] == "Maya Patel"
    assert body["doctor"]["name"] == "Dr. Ananya Sharma"
    assert body["slot"]["id"] == slot.id


def test_booking_same_slot_twice_is_409_slot_taken(login, db: Session) -> None:
    maya = login("patient")
    slot = _free_future_slot(db)
    assert maya.post("/api/appointments", json={"slot_id": slot.id, "reason": "first"}).status_code == 201

    response = maya.post("/api/appointments", json={"slot_id": slot.id, "reason": "second"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "slot_taken"


def test_two_patients_racing_for_one_slot_exactly_one_wins(test_session_factory: sessionmaker[Session], db: Session) -> None:
    # A barrier inside before_flush makes both writers pass the friendly check first,
    # so the only thing that can stop the second insert is the partial unique index.
    slot_id = _free_future_slot(db).id
    racers = [_user_id(db, "Jordan Lee"), _user_id(db, "Priya Shah")]
    barrier = threading.Barrier(2, timeout=10)
    outcomes: list[tuple] = []
    outcomes_lock = threading.Lock()

    def attempt(patient_id: int) -> None:
        session = test_session_factory()
        event.listen(session, "before_flush", lambda *_args: barrier.wait())
        try:
            appointment = book(session, patient_id=patient_id, slot_id=slot_id, reason="race")
            outcome = ("booked", appointment.id)
        except ServiceError as err:
            outcome = ("error", err.http_status, err.code)
        except Exception as exc:  # recorded so the assertion shows what went wrong
            outcome = ("unexpected", repr(exc))
        finally:
            session.close()
        with outcomes_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=attempt, args=(pid,)) for pid in racers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    kinds = sorted(outcome[0] for outcome in outcomes)
    assert kinds == ["booked", "error"], outcomes
    loser = next(outcome for outcome in outcomes if outcome[0] == "error")
    assert loser[1:] == (409, "slot_taken")
    booked_rows = db.scalar(
        select(func.count()).select_from(Appointment).where(Appointment.slot_id == slot_id, Appointment.status.in_(["booked"]))
    )
    assert booked_rows == 1


def test_booking_past_slot_is_422_slot_in_past(login, db: Session) -> None:
    maya = login("patient")
    past = _past_slot(db)

    response = maya.post("/api/appointments", json={"slot_id": past.id, "reason": "Too late"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "slot_in_past"


def test_booking_unknown_slot_is_404(login) -> None:
    response = login("patient").post("/api/appointments", json={"slot_id": 999999, "reason": "x"})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "slot_not_found"


def test_staff_books_for_another_patient_with_patient_id(login, db: Session) -> None:
    receptionist = login("receptionist")
    slot = _free_future_slot(db)
    jordan_id = _user_id(db, "Jordan Lee")

    response = receptionist.post("/api/appointments", json={"slot_id": slot.id, "reason": "Walk-in", "patient_id": jordan_id})

    assert response.status_code == 201
    assert response.json()["patient"]["id"] == jordan_id


def test_staff_booking_without_patient_id_is_422(login, db: Session) -> None:
    slot = _free_future_slot(db)

    response = login("admin").post("/api/appointments", json={"slot_id": slot.id, "reason": "x"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


def test_patient_sending_other_patient_id_is_403(login, db: Session) -> None:
    maya = login("patient")
    slot = _free_future_slot(db)
    jordan_id = _user_id(db, "Jordan Lee")

    response = maya.post("/api/appointments", json={"slot_id": slot.id, "reason": "x", "patient_id": jordan_id})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"
    assert db.scalar(select(func.count()).select_from(Appointment).where(Appointment.slot_id == slot.id)) == 0


def test_patient_sending_own_patient_id_is_allowed(login, db: Session) -> None:
    maya = login("patient")
    slot = _free_future_slot(db)

    response = maya.post("/api/appointments", json={"slot_id": slot.id, "reason": "x", "patient_id": _user_id(db, "Maya Patel")})

    assert response.status_code == 201


@pytest.mark.parametrize(
    "payload",
    [
        {"reason": "x"},
        {"slot_id": 1},
        {"slot_id": 1, "reason": ""},
        {"slot_id": 1, "reason": "   "},
        {"slot_id": 1, "reason": "x" * 201},
    ],
)
def test_invalid_booking_body_is_422_validation_error(login, payload: dict) -> None:
    response = login("patient").post("/api/appointments", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


# --- listing and visibility -------------------------------------------------

def test_patient_list_shows_only_own_appointments(login, db: Session) -> None:
    maya = login("patient")
    jordan_booking = _appointment_for(db, "Jordan Lee", "booked")

    items = maya.get("/api/appointments").json()

    assert items
    assert {item["patient"]["name"] for item in items} == {"Maya Patel"}
    assert jordan_booking.id not in {item["id"] for item in items}


def test_staff_list_shows_all_appointments(login, db: Session) -> None:
    total = db.scalar(select(func.count()).select_from(Appointment))

    items = login("receptionist").get("/api/appointments").json()

    assert len(items) == total
    assert len({item["patient"]["name"] for item in items}) > 1


def test_list_filters_by_status_and_orders_by_slot_start(login) -> None:
    maya = login("patient")

    booked = maya.get("/api/appointments?status=booked").json()
    completed = maya.get("/api/appointments?status=completed").json()

    assert booked and all(item["status"] == "booked" for item in booked)
    assert completed and all(item["status"] == "completed" for item in completed)
    starts = [item["slot"]["starts_at"] for item in booked]
    assert starts == sorted(starts)


def test_list_rejects_unknown_status_with_422(login) -> None:
    response = login("patient").get("/api/appointments?status=lost")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


# --- reschedule -------------------------------------------------------------

def test_reschedule_moves_appointment_and_frees_old_slot(login, db: Session) -> None:
    maya = login("patient")
    current = _maya_booked(maya)
    old_slot_id = current["slot"]["id"]
    doctor_id = current["doctor"]["id"]
    new_slot = _free_future_slot(db, current["doctor"]["name"])

    response = maya.post(f"/api/appointments/{current['id']}/reschedule", json={"slot_id": new_slot.id})

    assert response.status_code == 200
    assert response.json()["id"] == current["id"]
    assert response.json()["slot"]["id"] == new_slot.id
    free_ids = {slot["id"] for slot in maya.get(f"/api/doctors/{doctor_id}/slots?days=30").json()}
    assert old_slot_id in free_ids
    assert new_slot.id not in free_ids


def test_reschedule_to_taken_slot_is_409_and_keeps_old_slot(login, db: Session) -> None:
    maya = login("patient")
    current = _maya_booked(maya)
    jordan_slot_id = _appointment_for(db, "Jordan Lee", "booked").slot_id

    response = maya.post(f"/api/appointments/{current['id']}/reschedule", json={"slot_id": jordan_slot_id})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "slot_taken"
    assert maya.get("/api/appointments?status=booked").json()[0]["slot"]["id"] == current["slot"]["id"]


def test_reschedule_to_same_slot_is_409_slot_taken(login) -> None:
    maya = login("patient")
    current = _maya_booked(maya)

    response = maya.post(f"/api/appointments/{current['id']}/reschedule", json={"slot_id": current["slot"]["id"]})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "slot_taken"


def test_reschedule_completed_appointment_is_409_invalid_state(login) -> None:
    maya = login("patient")
    completed = maya.get("/api/appointments?status=completed").json()[0]

    response = maya.post(f"/api/appointments/{completed['id']}/reschedule", json={"slot_id": completed["slot"]["id"]})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_state"


# --- cancel -----------------------------------------------------------------

def test_cancel_then_cancel_again_is_409_invalid_state(login) -> None:
    maya = login("patient")
    current = _maya_booked(maya)

    first = maya.post(f"/api/appointments/{current['id']}/cancel")
    second = maya.post(f"/api/appointments/{current['id']}/cancel")

    assert first.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "invalid_state"


def test_cancel_then_reschedule_is_409_invalid_state(login, db: Session) -> None:
    maya = login("patient")
    current = _maya_booked(maya)
    new_slot = _free_future_slot(db, current["doctor"]["name"])
    maya.post(f"/api/appointments/{current['id']}/cancel")

    response = maya.post(f"/api/appointments/{current['id']}/reschedule", json={"slot_id": new_slot.id})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_state"


def test_cancelled_slot_becomes_bookable_again(login, db: Session) -> None:
    maya = login("patient")
    current = _maya_booked(maya)
    maya.post(f"/api/appointments/{current['id']}/cancel")

    response = login("patient").post("/api/appointments", json={"slot_id": current["slot"]["id"], "reason": "again"})

    assert response.status_code == 201


def test_completed_appointment_cannot_be_cancelled(login) -> None:
    maya = login("patient")
    completed = maya.get("/api/appointments?status=completed").json()[0]

    response = maya.post(f"/api/appointments/{completed['id']}/cancel")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_state"


def test_patient_cannot_cancel_another_patients_appointment(login, db: Session) -> None:
    jordan_booking = _appointment_for(db, "Jordan Lee", "booked")

    response = login("patient").post(f"/api/appointments/{jordan_booking.id}/cancel")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "appointment_not_found"
    db.refresh(jordan_booking)
    assert jordan_booking.status == "booked"


def test_patient_cannot_reschedule_another_patients_appointment(login, db: Session) -> None:
    jordan_booking = _appointment_for(db, "Jordan Lee", "booked")
    new_slot = _free_future_slot(db)

    response = login("patient").post(f"/api/appointments/{jordan_booking.id}/reschedule", json={"slot_id": new_slot.id})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "appointment_not_found"


def test_staff_can_cancel_any_patients_appointment(login, db: Session) -> None:
    jordan_booking = _appointment_for(db, "Jordan Lee", "booked")

    response = login("receptionist").post(f"/api/appointments/{jordan_booking.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_unknown_appointment_is_404(login) -> None:
    response = login("admin").post("/api/appointments/999999/cancel")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "appointment_not_found"


def test_service_book_rejects_past_slot_without_writing(db: Session) -> None:
    past = _past_slot(db)
    before = db.scalar(select(func.count()).select_from(Appointment))

    with pytest.raises(ServiceError) as excinfo:
        book(db, patient_id=_user_id(db, "Maya Patel"), slot_id=past.id, reason="x")

    assert excinfo.value.code == "slot_in_past"
    assert db.scalar(select(func.count()).select_from(Appointment)) == before
