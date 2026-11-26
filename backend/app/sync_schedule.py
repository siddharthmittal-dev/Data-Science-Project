"""Publish the next 30 clinic days, preserving every existing appointment and event."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.clinic import HOURS, slots_for_day, valid_slot
from app.config import get_settings
from app.db import SessionLocal
from app.models import Appointment, AppointmentEvent, Clinic, ClinicGuide, Doctor, Slot


def sync(db):
    now = datetime.now(ZoneInfo(get_settings().clinic_timezone))
    linked = set(db.scalars(select(Appointment.slot_id)))
    linked.update(db.scalars(select(AppointmentEvent.slot_id)))
    linked.update(db.scalars(select(AppointmentEvent.previous_slot_id)))
    for slot in db.scalars(select(Slot).where(Slot.starts_at > now)).all():
        if slot.id not in linked and not valid_slot(slot):
            db.execute(delete(Slot).where(Slot.id == slot.id))
    for doctor_id in db.scalars(select(Doctor.id)):
        for offset in range(31):
            for slot in slots_for_day(now.date() + timedelta(days=offset), doctor_id):
                if slot.starts_at > now:
                    db.execute(insert(Slot).values(doctor_id=doctor_id, starts_at=slot.starts_at,
                               ends_at=slot.ends_at).on_conflict_do_nothing(index_elements=["doctor_id", "starts_at"]))
    for clinic in db.scalars(select(Clinic)):
        clinic.hours = HOURS
    guide = db.scalar(select(ClinicGuide).where(ClinicGuide.slug == "opening-hours"))
    if guide:
        guide.body = f"Terra Family Clinic hours: {HOURS}. Last bookings start 30 minutes before closing."
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as db:
        sync(db)
    print("Published clinic schedule; existing appointments preserved.")
