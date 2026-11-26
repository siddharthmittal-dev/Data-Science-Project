from datetime import datetime, UTC
from types import SimpleNamespace

import httpx
from pydantic import SecretStr
from sqlalchemy import select, func

from app.models import Appointment, AppointmentEvent, Slot, User
from app.clinic import slots_for_day, valid_slot
from app.services.assistant import build_context
from app.services.assistant_provider import RuleBasedProvider
from app.services.cloudflare_provider import CloudflareProvider


def free(db):
    used = select(Appointment.slot_id).where(Appointment.status == "booked")
    return db.scalars(select(Slot).where(Slot.starts_at > datetime.now(UTC), Slot.id.not_in(used)).order_by(Slot.id)).first()


def test_staff_patient_selection_and_booking_retry(login, db):
    staff = login("receptionist")
    patients = staff.get("/api/appointments/patients")
    assert patients.status_code == 200
    patient_id = patients.json()[0]["id"]
    body = {"slot_id": free(db).id, "patient_id": patient_id, "reason": "Synthetic staff booking"}
    one = staff.post("/api/appointments", json=body, headers={"Idempotency-Key": "same-request"})
    two = staff.post("/api/appointments", json=body, headers={"Idempotency-Key": "same-request"})
    assert one.status_code == two.status_code == 201
    assert one.json()["id"] == two.json()["id"]
    assert db.scalar(select(func.count(AppointmentEvent.id)).where(AppointmentEvent.appointment_id == one.json()["id"])) == 1
    body["reason"] = "Different details"
    assert staff.post("/api/appointments", json=body, headers={"Idempotency-Key": "same-request"}).status_code == 409
    assert login("patient").get("/api/appointments/patients").status_code == 403


def test_same_doctor_and_final_outcomes(login, db):
    staff = login("admin")
    booking = staff.get("/api/appointments?status=booked").json()[0]
    original = db.get(Slot, booking["slot"]["id"])
    other = db.scalar(select(Slot).where(Slot.doctor_id != original.doctor_id, Slot.starts_at > datetime.now(UTC)))
    assert staff.post(f"/api/appointments/{booking['id']}/reschedule", json={"slot_id": other.id}).status_code == 422
    assert staff.post(f"/api/appointments/{booking['id']}/outcome", json={"status": "completed"}).status_code == 409
    past = db.scalar(select(Slot).where(Slot.ends_at < datetime.now(UTC)).order_by(Slot.id))
    appt = Appointment(patient_id=1, slot_id=past.id, status="booked", reason="Awaiting outcome")
    db.add(appt)
    db.commit()
    assert login("patient").post(f"/api/appointments/{appt.id}/outcome", json={"status": "completed"}).status_code == 403
    assert staff.post(f"/api/appointments/{appt.id}/outcome", json={"status": "completed"}).status_code == 200
    assert staff.post(f"/api/appointments/{appt.id}/outcome", json={"status": "no_show"}).status_code == 409
    assert db.scalar(select(AppointmentEvent.kind).where(AppointmentEvent.appointment_id == appt.id)) == "completed"


def test_confirmed_schedule_and_ambiguous_assistant(db):
    from datetime import date
    assert len(slots_for_day(date(2026, 11, 23), 1)) == 20
    assert len(slots_for_day(date(2026, 11, 21), 1)) == 8
    assert slots_for_day(date(2026, 11, 22), 1) == []
    assert all(valid_slot(s) for s in slots_for_day(date(2026, 11, 21), 1))
    context = build_context(db, db.get(User, 1))
    for message in ("book with someone", "book with a cardiologist and dermatologist", "book Dr Mehta tomorrow"):
        assert RuleBasedProvider().reply(message, context).proposed_action is None


def test_staff_assistant_requires_then_uses_selected_patient(login):
    staff = login("receptionist")
    assert staff.post("/api/assistant/message", json={"message": "book Dr Mehta"}).json()["proposed_action"] is None
    response = staff.post("/api/assistant/message", json={"message": "book Dr Mehta", "patient_id": 1})
    assert response.status_code == 200
    action = response.json()["proposed_action"]
    assert action["params"]["patient_id"] == 1
    assert "Maya Patel" in action["summary"]
    assert staff.post(f"/api/assistant/actions/{action['id']}/confirm").json()["appointment"]["patient"]["id"] == 1


def test_cloudflare_timeout_falls_back_and_never_runs_actions(db, monkeypatch):
    from app.services import cloudflare_provider
    context = build_context(db, db.get(User, 1))
    settings = SimpleNamespace(cloudflare_api_token=SecretStr("fake-test-token"), cloudflare_account_id="a" * 32,
                               cloudflare_model="@cf/meta/llama-3.1-8b-instruct")
    monkeypatch.setattr(cloudflare_provider, "get_settings", lambda: settings)
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(kwargs["json"])
        raise httpx.TimeoutException("test timeout")
    monkeypatch.setattr(cloudflare_provider.httpx, "post", unavailable)
    local = RuleBasedProvider().reply("opening hours", context)
    assert CloudflareProvider().reply("opening hours", context).reply == local.reply
    assert len(calls) == 1
    assert "Maya" not in str(calls)
    CloudflareProvider().reply("book Dr Mehta", context)
    assert len(calls) == 1


def test_replay_access_and_bad_date(login):
    assert login("patient").get("/api/insights/replay?origin=2026-11-09").status_code == 403
    staff = login("admin")
    assert staff.get("/api/insights/replay?origin=2026-11-09").status_code == 200
    assert staff.get("/api/insights/replay?origin=2026-11-20").status_code == 422
