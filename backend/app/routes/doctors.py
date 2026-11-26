from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from app.clinic import valid_slot
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Appointment, Clinic, Doctor, Slot, User

router = APIRouter(prefix="/doctors", tags=["doctors"])


class ClinicRef(BaseModel):
    id: int
    name: str


class DoctorOut(BaseModel):
    id: int
    name: str
    specialty: str
    bio: str
    clinic: ClinicRef
    next_available: datetime | None


class SlotOut(BaseModel):
    id: int
    starts_at: datetime
    ends_at: datetime


@router.get("", response_model=list[DoctorOut])
def list_doctors(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    occupied = select(Appointment.slot_id).where(Appointment.status == "booked")
    available = db.scalars(select(Slot).where(Slot.starts_at > datetime.now(UTC),
                               Slot.starts_at < datetime.now(UTC) + timedelta(days=14), Slot.id.not_in(occupied))
                          .order_by(Slot.starts_at)).all()
    earliest = {}
    for slot in available:
        if valid_slot(slot):
            earliest.setdefault(slot.doctor_id, slot.starts_at)
    rows = db.execute(select(Doctor, Clinic).join(Clinic, Doctor.clinic_id == Clinic.id).order_by(Doctor.id)).all()
    return [
        {
            "id": doctor.id,
            "name": doctor.name,
            "specialty": doctor.specialty,
            "bio": doctor.bio,
            "clinic": {"id": clinic.id, "name": clinic.name},
            "next_available": earliest.get(doctor.id),
        }
        for doctor, clinic in rows
    ]


@router.get("/{doctor_id}/slots", response_model=list[SlotOut])
def list_free_slots(
    doctor_id: int,
    days: int = Query(14, ge=1, le=30),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    if db.get(Doctor, doctor_id) is None:
        raise HTTPException(404, detail={"code": "doctor_not_found", "message": "That doctor does not exist."})
    now = datetime.now(UTC)
    booked = select(Appointment.slot_id).where(Appointment.status.in_(["booked"]))
    slots = db.scalars(
        select(Slot)
        .where(
            Slot.doctor_id == doctor_id,
            Slot.starts_at > now,
            Slot.starts_at < now + timedelta(days=days),
            Slot.id.not_in(booked),
        )
        .order_by(Slot.starts_at)
    ).all()
    return [{"id": s.id, "starts_at": s.starts_at, "ends_at": s.ends_at} for s in slots if valid_slot(s)]
