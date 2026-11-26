from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import STAFF_ROLES, get_current_user, require_staff
from app.models import Appointment, Doctor, Slot, User
from app.routes.doctors import SlotOut
from app.services.appointments import book, cancel, reschedule, record_outcome
from app.services.errors import ServiceError
from app.clinic import valid_slot

router = APIRouter(prefix="/appointments", tags=["appointments"])

Status = Literal["booked", "cancelled", "completed", "no_show"]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class PersonRef(BaseModel):
    id: int
    name: str


class DoctorRef(BaseModel):
    id: int
    name: str
    specialty: str


class AppointmentItem(BaseModel):
    id: int
    status: str
    reason: str
    patient: PersonRef
    doctor: DoctorRef
    slot: SlotOut
    legacy_schedule: bool


class BookIn(BaseModel):
    slot_id: int
    reason: Reason
    patient_id: int | None = None


class SlotIn(BaseModel):
    slot_id: int


def item_query():
    return (
        select(Appointment, Slot, Doctor, User)
        .join(Slot, Appointment.slot_id == Slot.id)
        .join(Doctor, Slot.doctor_id == Doctor.id)
        .join(User, Appointment.patient_id == User.id)
    )


def to_item(row, viewer: User) -> AppointmentItem:
    appointment, slot, doctor, patient = row
    return AppointmentItem(
        id=appointment.id,
        status=appointment.status,
        reason="" if viewer.role == "receptionist" else appointment.reason,
        patient=PersonRef(id=patient.id, name=patient.name),
        doctor=DoctorRef(id=doctor.id, name=doctor.name, specialty=doctor.specialty),
        slot=SlotOut(id=slot.id, starts_at=slot.starts_at, ends_at=slot.ends_at),
        legacy_schedule=not valid_slot(slot),
    )


def load_item(db: Session, appointment_id: int, viewer: User) -> AppointmentItem:
    return to_item(db.execute(item_query().where(Appointment.id == appointment_id)).one(), viewer)


def _http(err: ServiceError) -> HTTPException:
    return HTTPException(err.http_status, detail={"code": err.code, "message": err.message})


def _forbidden() -> HTTPException:
    return HTTPException(403, detail={"code": "forbidden", "message": "You can only change your own appointments."})


def _authorize_change(db: Session, user: User, appointment_id: int) -> None:
    owner_id = db.scalar(select(Appointment.patient_id).where(Appointment.id == appointment_id))
    if owner_id is None:
        raise HTTPException(404, detail={"code": "appointment_not_found", "message": "That appointment does not exist."})
    if user.role not in STAFF_ROLES and owner_id != user.id:
        raise HTTPException(404, detail={"code": "appointment_not_found", "message": "That appointment does not exist."})


@router.get("", response_model=list[AppointmentItem])
def list_appointments(
    status: Status | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AppointmentItem]:
    stmt = item_query().order_by(Slot.starts_at, Appointment.id)
    if user.role not in STAFF_ROLES:
        stmt = stmt.where(Appointment.patient_id == user.id)
    if status is not None:
        stmt = stmt.where(Appointment.status.in_([status]))
    return [to_item(row, user) for row in db.execute(stmt).all()]


@router.post("", status_code=201, response_model=AppointmentItem)
def create_appointment(
    body: BookIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=100),
) -> AppointmentItem:
    if user.role in STAFF_ROLES:
        if body.patient_id is None:
            raise HTTPException(
                422, detail={"code": "validation_error", "message": "Say which patient this appointment is for."}
            )
        patient_id = body.patient_id
    else:
        if body.patient_id not in (None, user.id):
            raise _forbidden()
        patient_id = user.id
    try:
        appointment = book(db, patient_id=patient_id, slot_id=body.slot_id, reason=body.reason,
                           actor_id=user.id, request_key=idempotency_key)
    except ServiceError as err:
        raise _http(err) from err
    return load_item(db, appointment.id, user)


@router.get("/patients", response_model=list[PersonRef])
def patients(_: User = Depends(require_staff), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.role == "patient").order_by(User.name)).all()


class OutcomeIn(BaseModel):
    status: Literal["completed", "no_show"]


@router.post("/{appointment_id}/outcome", response_model=AppointmentItem)
def outcome(appointment_id: int, body: OutcomeIn, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    try:
        appointment = record_outcome(db, appointment_id=appointment_id, status=body.status)
    except ServiceError as err:
        raise _http(err) from err
    return load_item(db, appointment.id, user)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentItem)
def reschedule_appointment(
    appointment_id: int,
    body: SlotIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentItem:
    _authorize_change(db, user, appointment_id)
    try:
        appointment = reschedule(db, appointment_id=appointment_id, new_slot_id=body.slot_id)
    except ServiceError as err:
        raise _http(err) from err
    return load_item(db, appointment.id, user)


@router.post("/{appointment_id}/cancel", response_model=AppointmentItem)
def cancel_appointment(
    appointment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppointmentItem:
    _authorize_change(db, user, appointment_id)
    try:
        appointment = cancel(db, appointment_id=appointment_id)
    except ServiceError as err:
        raise _http(err) from err
    return load_item(db, appointment.id, user)
