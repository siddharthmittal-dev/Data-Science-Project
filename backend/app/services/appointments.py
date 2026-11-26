"""The only code that changes appointments.

Appointment states: booked -> booked (reschedule), booked -> cancelled. Everything else is terminal.
Each move runs in one transaction. The partial unique index uq_appointments_slot_booked is the
double-booking guard; an IntegrityError on it becomes ServiceError 409 slot_taken.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json

from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentEvent, BookingRequest, Slot, User
from app.services.errors import ServiceError
from app.clinic import valid_slot

SLOT_GUARD = "uq_appointments_slot_booked"


def _is_slot_guard(exc: IntegrityError) -> bool:
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == SLOT_GUARD


@contextmanager
def _transaction(db: Session) -> Iterator[None]:
    try:
        yield
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_slot_guard(exc):
            raise ServiceError(409, "slot_taken", "That time slot was just taken. Pick another.") from exc
        raise
    except BaseException:
        db.rollback()
        raise


def _slot_or_404(db: Session, slot_id: int) -> Slot:
    slot = db.get(Slot, slot_id)
    if slot is None:
        raise ServiceError(404, "slot_not_found", "That time slot does not exist.")
    return slot


def _slot_is_taken(db: Session, slot_id: int) -> bool:
    return db.scalar(select(Appointment.id).where(Appointment.slot_id == slot_id, Appointment.status == "booked")) is not None


def _locked_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.scalar(select(Appointment).where(Appointment.id == appointment_id).with_for_update())
    if appointment is None:
        raise ServiceError(404, "appointment_not_found", "That appointment does not exist.")
    return appointment


def book(db: Session, *, patient_id: int, slot_id: int, reason: str, now: datetime | None = None,
         actor_id: int | None = None, request_key: str | None = None) -> Appointment:
    now = now or datetime.now(UTC)
    with _transaction(db):
        signature = hashlib.sha256(json.dumps([patient_id, slot_id, reason]).encode()).hexdigest()
        if request_key and actor_id is not None:
            # Serialize retries for this actor/key; slot uniqueness still guards different keys.
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                       {"key": f"booking:{actor_id}:{request_key}"})
            previous = db.get(BookingRequest, (actor_id, request_key))
            if previous:
                if previous.signature != signature:
                    raise ServiceError(409, "request_key_conflict", "This booking key was already used for different details.")
                return db.get(Appointment, previous.appointment_id)
        slot = _slot_or_404(db, slot_id)
        if slot.starts_at <= now:
            raise ServiceError(422, "slot_in_past", "That time has already passed.")
        if not valid_slot(slot):
            raise ServiceError(422, "outside_hours", "Choose a published time within clinic opening hours.")
        is_patient = db.scalar(select(User.id).where(User.id == patient_id, User.role == "patient"))
        if is_patient is None:
            raise ServiceError(404, "patient_not_found", "That patient does not exist.")
        if _slot_is_taken(db, slot_id):
            raise ServiceError(409, "slot_taken", "That time slot was just taken. Pick another.")
        appointment = Appointment(
            patient_id=patient_id,
            slot_id=slot_id,
            status="booked",
            reason=reason,
            created_at=now,
            updated_at=now,
        )
        db.add(appointment)
        db.flush()
        db.execute(insert(AppointmentEvent).values(appointment_id=appointment.id, kind="booked", slot_id=slot_id,
                                status="booked", occurred_at=now))
        if request_key and actor_id is not None:
            db.execute(insert(BookingRequest).values(actor_id=actor_id, key=request_key, signature=signature,
                                                     appointment_id=appointment.id))
    return appointment


def reschedule(db: Session, *, appointment_id: int, new_slot_id: int, now: datetime | None = None) -> Appointment:
    now = now or datetime.now(UTC)
    with _transaction(db):
        appointment = _locked_appointment(db, appointment_id)
        if appointment.status != "booked" or db.get(Slot, appointment.slot_id).starts_at <= now:
            raise ServiceError(409, "invalid_state", "Only an upcoming booked appointment can be rescheduled.")
        if new_slot_id == appointment.slot_id:
            raise ServiceError(409, "slot_taken", "That is already your time slot.")
        new_slot = _slot_or_404(db, new_slot_id)
        if new_slot.doctor_id != db.get(Slot, appointment.slot_id).doctor_id:
            raise ServiceError(422, "different_doctor", "Choose another time with the same doctor.")
        if new_slot.starts_at <= now:
            raise ServiceError(422, "slot_in_past", "That time has already passed.")
        if not valid_slot(new_slot):
            raise ServiceError(422, "outside_hours", "Choose a time within clinic opening hours.")
        if _slot_is_taken(db, new_slot_id):
            raise ServiceError(409, "slot_taken", "That time slot was just taken. Pick another.")
        previous_slot_id = appointment.slot_id
        appointment.slot_id = new_slot_id
        appointment.updated_at = now
        db.flush()
        db.execute(insert(AppointmentEvent).values(appointment_id=appointment.id, kind="rescheduled", slot_id=new_slot_id,
                                previous_slot_id=previous_slot_id, status="booked", occurred_at=now))
    return appointment


def cancel(db: Session, *, appointment_id: int) -> Appointment:
    now = datetime.now(UTC)
    with _transaction(db):
        appointment = _locked_appointment(db, appointment_id)
        if appointment.status != "booked":
            raise ServiceError(409, "invalid_state", "Only a booked appointment can be cancelled.")
        appointment.status = "cancelled"
        appointment.updated_at = now
        db.flush()
        db.execute(insert(AppointmentEvent).values(appointment_id=appointment.id, kind="cancelled", slot_id=appointment.slot_id,
                                status="cancelled", occurred_at=now))
    return appointment


def record_outcome(db: Session, *, appointment_id: int, status: str, now: datetime | None = None) -> Appointment:
    if status not in ("completed", "no_show"):
        raise ServiceError(422, "invalid_outcome", "Choose completed or no-show.")
    now = now or datetime.now(UTC)
    with _transaction(db):
        appointment = _locked_appointment(db, appointment_id)
        if appointment.status != "booked" or db.get(Slot, appointment.slot_id).ends_at > now:
            raise ServiceError(409, "invalid_state", "Record an outcome only after a booked visit has ended.")
        appointment.status = status
        appointment.updated_at = now
        db.flush()
        db.execute(insert(AppointmentEvent).values(appointment_id=appointment.id, kind=status,
                   slot_id=appointment.slot_id, status=status, occurred_at=now))
    return appointment
