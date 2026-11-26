import threading
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Appointment, AssistantAction, Doctor, Slot, User
from app.services import assistant
from app.services.appointments import book
from app.services.assistant_provider import (
    REFUSAL,
    AppointmentRef,
    AssistantContext,
    DoctorRef,
    FreeSlot,
    GuideRef,
    RuleBasedProvider,
)
from app.services.errors import ServiceError

MESSAGE = "/api/assistant/message"


def _user_id(db: Session, name: str) -> int:
    return db.scalar(select(User.id).where(User.name == name))


def _doctor_id(db: Session, name: str) -> int:
    return db.scalar(select(Doctor.id).where(Doctor.name == name))


def _earliest_free_slot_id(db: Session, doctor_name: str) -> int:
    booked = select(Appointment.slot_id).where(Appointment.status.in_(["booked"]))
    stmt = (
        select(Slot.id)
        .join(Doctor, Slot.doctor_id == Doctor.id)
        .where(Doctor.name == doctor_name, Slot.starts_at > datetime.now(UTC), Slot.id.not_in(booked))
        .order_by(Slot.starts_at, Slot.id)
    )
    return db.scalars(stmt).first()


def _booked_for(db: Session, patient_name: str) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .join(User, Appointment.patient_id == User.id)
            .join(Slot, Appointment.slot_id == Slot.id)
            .where(User.name == patient_name, Appointment.status.in_(["booked"]))
            .order_by(Slot.starts_at)
        )
    )


def _action_status(db: Session, action_id: int) -> str | None:
    return db.scalar(select(AssistantAction.status).where(AssistantAction.id == action_id))


def _action_count(db: Session) -> int:
    return db.scalar(select(func.count(AssistantAction.id)))


def _ask(client: TestClient, text: str):
    return client.post(MESSAGE, json={"message": text})


def _propose_cancel(client: TestClient) -> dict:
    response = _ask(client, "cancel my appointment")
    assert response.status_code == 200, response.text
    proposal = response.json()["proposed_action"]
    assert proposal is not None
    return proposal


# --- provider unit tests (no HTTP, no DB) ---------------------------------------------

GUIDES = [
    GuideRef("opening-hours", "Opening hours", "Terra Family Clinic is open Monday to Friday from 8:00 to 18:00. We are closed on Sunday."),
    GuideRef("booking-and-rescheduling", "Booking and rescheduling", "Choose a doctor and a free time slot. Only upcoming booked appointments can be rescheduled."),
    GuideRef("cancellation-policy", "Cancellation policy", "You can cancel for free until 24 hours before its start time."),
    GuideRef("what-to-bring", "What to bring", "Bring a photo ID and your health card. Arrive 10 minutes early."),
    GuideRef("parking-and-directions", "Parking and directions", "We are at 12 Terra Lane. Free parking is available behind the building."),
    GuideRef("privacy-and-demo-notice", "Privacy and demo notice", "This is a demo. All patients are fictional."),
]
DOCTORS = [
    DoctorRef(1, "Dr. Ananya Sharma", "Family Medicine"),
    DoctorRef(2, "Dr. Arjun Mehta", "Pediatrics"),
    DoctorRef(3, "Dr. Kavya Rao", "Dermatology"),
]
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def _context(upcoming=(), free=None) -> AssistantContext:
    free = free or {}
    return AssistantContext(
        user_id=1,
        guides=GUIDES,
        doctors=DOCTORS,
        upcoming=list(upcoming),
        earliest_free_slot=lambda doctor_id: free.get(doctor_id),
    )


def _appt(appointment_id: int, doctor: DoctorRef, starts_at: datetime, slot_id: int) -> AppointmentRef:
    return AppointmentRef(
        id=appointment_id, slot_id=slot_id, doctor_id=doctor.id, doctor_name=doctor.name, specialty=doctor.specialty, starts_at=starts_at
    )


def test_provider_refuses_off_topic_questions() -> None:
    provider = RuleBasedProvider()
    for text in ["what is the capital of France", "diagnose my rash"]:
        result = provider.reply(text, _context())
        assert result.reply == "I can only help with Terra Family Clinic information and your appointments."
        assert result.citations == []
        assert result.proposed_action is None


def test_provider_refusal_constant_is_exact() -> None:
    assert REFUSAL == "I can only help with Terra Family Clinic information and your appointments."


def test_provider_hours_question_cites_opening_hours_guide() -> None:
    result = RuleBasedProvider().reply("What are your opening hours?", _context())

    assert result.citations == [{"slug": "opening-hours", "title": "Opening hours"}]
    assert result.reply.startswith("Terra Family Clinic is open Monday to Friday")
    assert result.proposed_action is None


def test_provider_parking_question_cites_parking_guide() -> None:
    result = RuleBasedProvider().reply("Where can I park and what is the address?", _context())

    assert result.citations == [{"slug": "parking-and-directions", "title": "Parking and directions"}]


def test_provider_cancellation_policy_question_is_guide_not_action() -> None:
    result = RuleBasedProvider().reply(
        "What is your cancellation policy?", _context([_appt(7, DOCTORS[0], NOW, 70)])
    )

    assert result.citations == [{"slug": "cancellation-policy", "title": "Cancellation policy"}]
    assert result.proposed_action is None


def test_provider_cancel_proposes_next_upcoming_appointment() -> None:
    upcoming = [_appt(7, DOCTORS[0], NOW, 70), _appt(8, DOCTORS[1], NOW.replace(day=5), 80)]

    result = RuleBasedProvider().reply("please cancel my visit", _context(upcoming))

    assert result.proposed_action == {
        "type": "cancel",
        "params": {"appointment_id": 7},
        "summary": "Cancel your appointment with Dr. Ananya Sharma on Mon 2 Nov, 14:30",
    }


def test_provider_cancel_without_upcoming_appointments_says_so() -> None:
    result = RuleBasedProvider().reply("cancel my appointment", _context())

    assert result.reply == "You have no upcoming appointments to cancel."
    assert result.proposed_action is None


def test_provider_reschedule_proposes_earliest_free_slot_of_same_doctor() -> None:
    upcoming = [_appt(7, DOCTORS[0], NOW, 70)]
    free = {DOCTORS[0].id: FreeSlot(id=99, doctor_id=1, starts_at=NOW.replace(day=3, hour=10))}

    result = RuleBasedProvider().reply("I want to move my appointment", _context(upcoming, free))

    assert result.proposed_action["type"] == "reschedule"
    assert result.proposed_action["params"] == {"appointment_id": 7, "slot_id": 99}


def test_provider_reschedule_without_free_slot_says_so() -> None:
    upcoming = [_appt(7, DOCTORS[0], NOW, 70)]

    result = RuleBasedProvider().reply("reschedule my appointment", _context(upcoming))

    assert result.proposed_action is None
    assert "no free slot" in result.reply.lower()


@pytest.mark.parametrize("text", ["book me with a pediatrician", "book with Dr. Mehta", "schedule with pediatrics", "appointment with Arjun"])
def test_provider_book_matches_doctor_by_specialty_or_name(text: str) -> None:
    free = {DOCTORS[1].id: FreeSlot(id=55, doctor_id=2, starts_at=NOW.replace(day=3, hour=9))}

    result = RuleBasedProvider().reply(text, _context(free=free))

    assert result.proposed_action == {
        "type": "book",
        "params": {"slot_id": 55, "reason": "Booked via assistant"},
        "summary": "Book Dr. Arjun Mehta (Pediatrics) on Tue 3 Nov, 14:30",
    }


def test_provider_book_with_someone_does_not_match_a_doctor() -> None:
    result = RuleBasedProvider().reply("book with someone", _context())

    assert result.proposed_action is None
    assert result.citations == []
    assert "Which doctor or specialty" in result.reply


def test_provider_upcoming_lists_up_to_three_without_action() -> None:
    upcoming = [_appt(i, DOCTORS[0], NOW.replace(day=i + 2), i) for i in range(1, 5)]

    result = RuleBasedProvider().reply("show my upcoming appointments", _context(upcoming))

    assert result.proposed_action is None
    assert result.reply.count("Dr. Ananya Sharma") == 3


# --- auth and validation -------------------------------------------------------------

@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", MESSAGE),
        ("post", "/api/assistant/actions/1/confirm"),
        ("post", "/api/assistant/actions/1/dismiss"),
    ],
)
def test_assistant_endpoints_require_login(client: TestClient, method: str, path: str) -> None:
    response = client.request(method.upper(), path, json={"message": "hours"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthenticated"


@pytest.mark.parametrize("message", ["", "   ", "x" * 501])
def test_message_validation_rejects_empty_and_too_long(login, message: str) -> None:
    maya = login("patient")

    response = _ask(maya, message)

    assert response.status_code == 422


def test_message_of_500_chars_is_accepted(login) -> None:
    maya = login("patient")

    response = _ask(maya, "hours " * 83 + "xy")

    assert response.status_code == 200


# --- message endpoint: guides, refusal, listing -------------------------------------

def test_hours_question_returns_guide_citation_and_no_action(login, db: Session) -> None:
    maya = login("patient")

    body = _ask(maya, "What are your opening hours?").json()

    assert body["citations"] == [{"slug": "opening-hours", "title": "Opening hours"}]
    assert body["proposed_action"] is None
    assert _action_count(db) == 0


def test_parking_question_returns_parking_citation(login) -> None:
    maya = login("patient")

    body = _ask(maya, "Is there parking at the clinic?").json()

    assert body["citations"] == [{"slug": "parking-and-directions", "title": "Parking and directions"}]


def test_off_topic_question_gets_exact_refusal_and_no_action(login, db: Session) -> None:
    maya = login("patient")

    for text in ["what is the capital of France", "diagnose my rash"]:
        body = _ask(maya, text).json()
        assert body == {
            "reply": "I can only help with Terra Family Clinic information and your appointments.",
            "citations": [],
            "proposed_action": None,
        }
    assert _action_count(db) == 0


def test_my_appointments_lists_upcoming_without_action(login, db: Session) -> None:
    maya = login("patient")

    body = _ask(maya, "what are my upcoming appointments").json()

    assert "Dr. Ananya Sharma" in body["reply"]
    assert body["proposed_action"] is None
    assert _action_count(db) == 0


# --- cancel / confirm / dismiss ------------------------------------------------------

def test_cancel_message_creates_pending_action_and_does_not_cancel(login, db: Session) -> None:
    maya = login("patient")
    booked_before = len(_booked_for(db, "Maya Patel"))

    proposal = _propose_cancel(maya)

    assert proposal["type"] == "cancel"
    assert set(proposal) == {"id", "type", "summary", "params"}
    assert proposal["summary"].startswith("Cancel your appointment with Dr. Ananya Sharma on ")
    assert _action_status(db, proposal["id"]) == "pending"
    assert len(_booked_for(db, "Maya Patel")) == booked_before


def test_confirm_cancel_cancels_the_appointment(login, db: Session) -> None:
    maya = login("patient")
    proposal = _propose_cancel(maya)
    target_id = proposal["params"]["appointment_id"]

    response = maya.post(f"/api/assistant/actions/{proposal['id']}/confirm")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "confirmed"
    assert set(body["appointment"]) == {"id", "status", "reason", "patient", "doctor", "slot", "legacy_schedule"}
    assert body["appointment"]["id"] == target_id
    assert body["appointment"]["status"] == "cancelled"
    db.expire_all()
    assert db.scalar(select(Appointment.status).where(Appointment.id == target_id)) == "cancelled"
    assert _action_status(db, proposal["id"]) == "confirmed"


def test_second_confirm_is_409_invalid_state(login) -> None:
    maya = login("patient")
    proposal = _propose_cancel(maya)
    assert maya.post(f"/api/assistant/actions/{proposal['id']}/confirm").status_code == 200

    response = maya.post(f"/api/assistant/actions/{proposal['id']}/confirm")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_state"


def test_dismiss_then_confirm_is_409_and_nothing_changes(login, db: Session) -> None:
    maya = login("patient")
    proposal = _propose_cancel(maya)
    target_id = proposal["params"]["appointment_id"]

    dismissed = maya.post(f"/api/assistant/actions/{proposal['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json() == {"status": "dismissed"}

    response = maya.post(f"/api/assistant/actions/{proposal['id']}/confirm")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_state"
    assert _action_status(db, proposal["id"]) == "dismissed"
    db.expire_all()
    assert db.scalar(select(Appointment.status).where(Appointment.id == target_id)) == "booked"


def test_confirm_by_another_user_is_404_and_action_stays_pending(login, db: Session) -> None:
    maya = login("patient")
    proposal = _propose_cancel(maya)
    sam = login("receptionist")

    confirm = sam.post(f"/api/assistant/actions/{proposal['id']}/confirm")
    dismiss = sam.post(f"/api/assistant/actions/{proposal['id']}/dismiss")

    assert confirm.status_code == 404
    assert confirm.json()["detail"]["code"] == "action_not_found"
    assert dismiss.status_code == 404
    assert _action_status(db, proposal["id"]) == "pending"


def test_confirm_missing_action_is_404(login) -> None:
    maya = login("patient")

    response = maya.post("/api/assistant/actions/999999/confirm")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "action_not_found"


def test_patient_cannot_confirm_action_targeting_someone_elses_appointment(login, db: Session) -> None:
    maya = login("patient")
    jordan_appointment = _booked_for(db, "Jordan Lee")[0]
    action = AssistantAction(
        user_id=_user_id(db, "Maya Patel"),
        type="cancel",
        params={"appointment_id": jordan_appointment.id},
        summary="Cancel Jordan's appointment",
        status="pending",
    )
    db.add(action)
    db.commit()

    response = maya.post(f"/api/assistant/actions/{action.id}/confirm")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"
    assert _action_status(db, action.id) == "pending"
    db.expire_all()
    assert db.scalar(select(Appointment.status).where(Appointment.id == jordan_appointment.id)) == "booked"


def test_cancel_with_no_appointments_gets_reply_and_no_action(login, db: Session) -> None:
    sam = login("receptionist")

    body = _ask(sam, "cancel my appointment").json()

    assert "Which patient" in body["reply"]
    assert body["proposed_action"] is None
    assert _action_count(db) == 0


def test_new_proposal_dismisses_older_pending_action(login, db: Session) -> None:
    maya = login("patient")
    older = _propose_cancel(maya)
    newer = _ask(maya, "move my appointment").json()["proposed_action"]

    assert newer["id"] != older["id"]
    assert _action_status(db, older["id"]) == "dismissed"
    assert _action_status(db, newer["id"]) == "pending"
    assert maya.post(f"/api/assistant/actions/{older['id']}/confirm").status_code == 409


# --- reschedule and book -------------------------------------------------------------

def test_reschedule_proposal_targets_same_doctor_earliest_free_slot_and_confirm_moves_it(login, db: Session) -> None:
    maya = login("patient")
    next_appointment = _booked_for(db, "Maya Patel")[0]
    expected_slot = _earliest_free_slot_id(db, "Dr. Ananya Sharma")

    body = _ask(maya, "please reschedule my next appointment").json()
    proposal = body["proposed_action"]

    assert proposal["type"] == "reschedule"
    assert proposal["params"] == {"appointment_id": next_appointment.id, "slot_id": expected_slot}
    assert "Dr. Ananya Sharma" in proposal["summary"]

    response = maya.post(f"/api/assistant/actions/{proposal['id']}/confirm")

    assert response.status_code == 200, response.text
    assert response.json()["appointment"]["slot"]["id"] == expected_slot
    db.expire_all()
    assert db.scalar(select(Appointment.slot_id).where(Appointment.id == next_appointment.id)) == expected_slot


def test_book_pediatrician_proposal_confirm_creates_booked_appointment(login, db: Session) -> None:
    maya = login("patient")
    expected_slot = _earliest_free_slot_id(db, "Dr. Arjun Mehta")

    proposal = _ask(maya, "book me with a pediatrician").json()["proposed_action"]

    assert proposal["type"] == "book"
    assert proposal["params"] == {"slot_id": expected_slot, "reason": "Booked via assistant"}

    response = maya.post(f"/api/assistant/actions/{proposal['id']}/confirm")

    assert response.status_code == 200, response.text
    appointment = response.json()["appointment"]
    assert appointment["status"] == "booked"
    assert appointment["doctor"] == {"id": _doctor_id(db, "Dr. Arjun Mehta"), "name": "Dr. Arjun Mehta", "specialty": "Pediatrics"}
    assert appointment["patient"]["name"] == "Maya Patel"
    assert appointment["slot"]["id"] == expected_slot


def test_confirm_when_slot_was_taken_is_409_slot_taken_and_action_fails(login, db: Session) -> None:
    maya = login("patient")
    slot_id = _earliest_free_slot_id(db, "Dr. Arjun Mehta")
    proposal = _ask(maya, "book me with a pediatrician").json()["proposed_action"]
    book(db, patient_id=_user_id(db, "Jordan Lee"), slot_id=slot_id, reason="someone else")

    response = maya.post(f"/api/assistant/actions/{proposal['id']}/confirm")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "slot_taken"
    assert _action_status(db, proposal["id"]) == "failed"
    assert maya.post(f"/api/assistant/actions/{proposal['id']}/confirm").status_code == 409


def test_failed_service_error_is_surfaced_not_swallowed(login, db: Session, monkeypatch) -> None:
    maya = login("patient")
    proposal = _propose_cancel(maya)

    def refuse(*_args, **_kwargs):
        raise ServiceError(409, "invalid_state", "Only a booked appointment can be cancelled.")

    monkeypatch.setattr(assistant, "cancel", refuse)

    response = maya.post(f"/api/assistant/actions/{proposal['id']}/confirm")

    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "invalid_state", "message": "Only a booked appointment can be cancelled."}
    assert _action_status(db, proposal["id"]) == "failed"


# --- concurrency ----------------------------------------------------------------------

def test_two_concurrent_confirms_yield_exactly_one_success(login, db: Session, test_session_factory: sessionmaker) -> None:
    maya = login("patient")
    proposal = _propose_cancel(maya)
    maya_id = _user_id(db, "Maya Patel")
    cancelled_before = db.scalar(
        select(func.count(Appointment.id)).where(Appointment.patient_id == maya_id, Appointment.status.in_(["cancelled"]))
    )
    barrier = threading.Barrier(2, timeout=10)
    outcomes: list[tuple] = []
    lock = threading.Lock()

    def attempt() -> None:
        session = test_session_factory()
        try:
            user = session.get(User, maya_id)
            barrier.wait()
            result = assistant.confirm(session, user, proposal["id"])
            outcome = ("ok", result.id)
        except ServiceError as err:
            outcome = ("error", err.http_status, err.code)
        except Exception as exc:  # recorded so the assertion shows what went wrong
            outcome = ("unexpected", repr(exc))
        finally:
            session.close()
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    kinds = sorted(outcome[0] for outcome in outcomes)
    assert kinds == ["error", "ok"], outcomes
    assert ("error", 409, "invalid_state") in outcomes
    db.expire_all()
    cancelled_after = db.scalar(
        select(func.count(Appointment.id)).where(Appointment.patient_id == maya_id, Appointment.status.in_(["cancelled"]))
    )
    assert cancelled_after == cancelled_before + 1
    assert _action_status(db, proposal["id"]) == "confirmed"
