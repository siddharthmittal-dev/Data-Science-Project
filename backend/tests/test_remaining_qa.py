"""Focused remaining-MVP QA; fixtures are confined to the guarded test database."""
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models import Appointment, AppointmentEvent, Slot, User, UserSession
from app.services.assistant import build_context
from app.services.assistant_provider import RuleBasedProvider


@pytest.mark.parametrize("slug", [
    "opening-hours", "booking-and-rescheduling", "cancellation-policy",
    "what-to-bring", "parking-and-directions", "privacy-and-demo-notice",
])
def test_all_reader_sources_are_available(login, slug):
    guide = login("patient").get(f"/api/guides/{slug}")
    assert guide.status_code == 200
    assert guide.json()["slug"] == slug
    assert guide.json()["body"].strip()


@pytest.mark.parametrize("question,slug", [
    ("What are your opening hours?", "opening-hours"),
    ("What is your cancellation policy?", "cancellation-policy"),
    ("What should I bring?", "what-to-bring"),
    ("Where do I park?", "parking-and-directions"),
])
def test_information_questions_cite_the_matching_reader(login, question, slug):
    reply = login("patient").post("/api/assistant/message", json={"message": question}).json()
    assert reply["proposed_action"] is None
    assert [citation["slug"] for citation in reply["citations"]] == [slug]


def test_booking_process_question_is_information_not_reschedule(db):
    context = build_context(db, db.get(User, 1))
    reply = RuleBasedProvider().reply("How does booking and rescheduling work?", context)
    assert reply.proposed_action is None
    assert [c["slug"] for c in reply.citations] == ["booking-and-rescheduling"]


def test_privacy_policy_question_cites_privacy(db):
    context = build_context(db, db.get(User, 1))
    reply = RuleBasedProvider().reply("What is your privacy policy?", context)
    assert reply.proposed_action is None
    assert [c["slug"] for c in reply.citations] == ["privacy-and-demo-notice"]


def test_switching_staff_patient_invalidates_older_proposal_without_booking(login, db):
    staff = login("receptionist")
    before = db.scalar(select(func.count(Appointment.id)))
    maya = db.scalar(select(User.id).where(User.name == "Maya Patel"))
    jordan = db.scalar(select(User.id).where(User.name == "Jordan Lee"))
    one = staff.post("/api/assistant/message", json={"message": "book Dr Mehta", "patient_id": maya}).json()["proposed_action"]
    two = staff.post("/api/assistant/message", json={"message": "book Dr Mehta", "patient_id": jordan}).json()["proposed_action"]
    assert "Maya Patel" in one["summary"] and "Jordan Lee" in two["summary"]
    assert staff.post(f"/api/assistant/actions/{one['id']}/confirm").status_code == 409
    assert db.scalar(select(func.count(Appointment.id))) == before
    assert staff.post(f"/api/assistant/actions/{two['id']}/dismiss").status_code == 200
    assert staff.post(f"/api/assistant/actions/{two['id']}/confirm").status_code == 409


def test_no_show_event_and_reporting_reconcile(login, db):
    slot = db.scalars(select(Slot).where(Slot.ends_at < datetime.now(UTC)).order_by(Slot.starts_at.desc())).first()
    appointment = Appointment(patient_id=1, slot_id=slot.id, status="booked", reason="Synthetic no-show QA")
    db.add(appointment)
    db.commit()
    staff = login("admin")
    before = staff.get("/api/insights").json()["totals"]["no_show"]
    result = staff.post(f"/api/appointments/{appointment.id}/outcome", json={"status": "no_show"})
    assert result.status_code == 200 and result.json()["status"] == "no_show"
    assert staff.get("/api/insights").json()["totals"]["no_show"] == before + 1
    assert db.scalar(select(AppointmentEvent.kind).where(AppointmentEvent.appointment_id == appointment.id)) == "no_show"
    assert staff.post(f"/api/appointments/{appointment.id}/outcome", json={"status": "completed"}).status_code == 409


@pytest.mark.parametrize("origin", ["", "not-a-date", "2020-01-01", "2099-01-01"])
def test_replay_bad_dates_fail_without_server_error(login, origin):
    assert login("admin").get("/api/insights/replay", params={"origin": origin}).status_code == 422


def test_expired_session_is_rejected_without_changing_visits(login, db):
    patient = login("patient")
    before = db.scalar(select(func.count(Appointment.id)))
    session = db.get(UserSession, patient.cookies.get("session"))
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert patient.get("/api/appointments").status_code == 401
    assert patient.post("/api/assistant/message", json={"message": "book Dr Mehta"}).status_code == 401
    assert db.scalar(select(func.count(Appointment.id))) == before


@pytest.mark.parametrize("origin,allowed", [
    ("http://localhost:3000", True), ("https://unrelated.invalid", False),
])
def test_cors_preflight_uses_configured_local_origin(client, origin, allowed):
    response = client.options("/api/appointments", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == (200 if allowed else 400)
    assert (response.headers.get("access-control-allow-origin") == origin) is allowed


def test_patient_cannot_write_follow_up_records(login):
    patient = login("patient")
    assert patient.post("/api/retention/tasks", json={"patient_id": 1, "note": "QA"}).status_code == 403
    assert patient.post("/api/retention/tasks/1/complete", json={"outcome": "QA"}).status_code == 403


def test_muted_body_text_contrast():
    css = (Path(__file__).resolve().parents[2] / "frontend/app/globals.css").read_text(encoding="utf-8")

    def luminance(name):
        color = re.search(rf"--{name}:\s*#([0-9a-f]{{6}})", css).group(1)
        channels = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, [0.2126, 0.7152, 0.0722]))

    dark, light = sorted([luminance("muted"), luminance("bg")])
    assert (light + 0.05) / (dark + 0.05) >= 4.5


@pytest.mark.parametrize("question,slug", [
    ("How do I cancel my appointment?", "cancellation-policy"),
    ("Please explain booking and rescheduling", "booking-and-rescheduling"),
    ("What is your privacy policy?", "privacy-and-demo-notice"),
])
def test_process_questions_only_provide_information(db, question, slug):
    context = build_context(db, db.get(User, 1))
    reply = RuleBasedProvider().reply(question, context)
    assert reply.proposed_action is None
    assert [c["slug"] for c in reply.citations] == [slug]


def test_refetched_doctor_availability_advances_after_booking(login):
    patient = login("patient")
    doctor = patient.get("/api/doctors").json()[0]
    slots = patient.get(f"/api/doctors/{doctor['id']}/slots").json()
    assert slots[0]["starts_at"] == doctor["next_available"]
    response = patient.post("/api/appointments", json={"slot_id": slots[0]["id"], "reason": "Synthetic availability refresh QA"})
    assert response.status_code == 201
    refreshed = next(d for d in patient.get("/api/doctors").json() if d["id"] == doctor["id"])
    assert refreshed["next_available"] == slots[1]["starts_at"]


def test_retention_missing_corrupt_stale_future_and_zero_scale_fall_back(monkeypatch):
    from app.services import retention

    artifact = json.loads(retention.ARTIFACT.read_text(encoding="utf-8"))
    today = datetime.now(UTC).date()

    def missing(**_kwargs):
        raise FileNotFoundError("Synthetic missing-artifact test")

    reader = SimpleNamespace(read_text=missing)
    monkeypatch.setattr(retention, "ARTIFACT", reader)
    assert retention.load_model(today) is None
    reader.read_text = lambda **_kwargs: "invalid json"
    assert retention.load_model(today) is None
    artifact["observation_end"] = (today - timedelta(days=31)).isoformat()
    reader.read_text = lambda **_kwargs: json.dumps(artifact)
    assert retention.load_model(today) is None
    artifact["observation_end"] = (today + timedelta(days=1)).isoformat()
    assert retention.load_model(today) is None
    artifact["observation_end"] = today.isoformat()
    artifact["model"]["scale"][0] = 0
    assert retention.load_model(today) is None
