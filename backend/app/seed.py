"""Deterministic synthetic demo data. Run with: python -m app.seed

Every run truncates the seeded tables and inserts the same content (fixed random seed,
dates relative to the day of the run), so running it twice leaves one copy.
All names, emails and contact details are fictional.
"""

import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models as m
from app.clinic import HOURS, slots_for_day

RANDOM_SEED = 42
TABLES = (
    "assistant_actions",
    "sessions",
    "appointments",
    "slots",
    "doctors",
    "users",
    "clinics",
    "clinic_guides",
    "daily_counts",
)

DOCTORS = [
    ("Dr. Ananya Sharma", "Family Medicine", "Leads general adult care, chronic condition reviews and preventive check-ups."),
    ("Dr. Arjun Mehta", "Pediatrics", "Cares for infants, children and teenagers, from routine vaccines to growth checks."),
    ("Dr. Kavya Rao", "Dermatology", "Treats skin conditions such as rashes, acne and moles, with mole checks by appointment."),
    ("Dr. Rohan Iyer", "Cardiology", "Reviews heart health, blood pressure and cholesterol, with referral support."),
    ("Dr. Nisha Verma", "Physiotherapy", "Helps with back, joint and sports injuries through guided movement plans."),
    ("Dr. Meera Kapoor", "Women's Health", "Provides sexual and reproductive health care, screening and pregnancy follow-up."),
]

USERS = [
    ("Maya Patel", "maya.patel@terra.example", "patient"),
    ("Sam Rivera", "sam.rivera@terra.example", "receptionist"),
    ("Dr. Alex Chen", "alex.chen@terra.example", "admin"),
    ("Jordan Lee", "jordan.lee@terra.example", "patient"),
    ("Priya Shah", "priya.shah@terra.example", "patient"),
]

GUIDES = [
    (
        "opening-hours",
        "Opening hours",
        f"Terra Family Clinic hours: {HOURS}. "
        "We are closed on Sunday and on public holidays. Last bookings start 30 minutes before closing.",
    ),
    (
        "booking-and-rescheduling",
        "Booking and rescheduling",
        "Choose a doctor and a free time slot in the Doctors section. Each visit is 30 minutes. "
        "To move a visit, open your appointment and pick another free slot with the same doctor. "
        "Only upcoming booked appointments can be rescheduled.",
    ),
    (
        "cancellation-policy",
        "Cancellation policy",
        "You can cancel an appointment for free until 24 hours before its start time. "
        "Cancelling later than that still works, but please call the front desk so we can offer the slot to someone else.",
    ),
    (
        "what-to-bring",
        "What to bring",
        "Bring a photo ID and your health card or insurance details. Bring a list of current medicines, "
        "and any recent test results or referral letters. Arrive 10 minutes early for a first visit.",
    ),
    (
        "parking-and-directions",
        "Parking and directions",
        "We are at 12 Terra Lane. Free parking is available in the clinic car park behind the building, "
        "with step-free access through the side entrance. Street parking is limited to two hours.",
    ),
    (
        "privacy-and-demo-notice",
        "Privacy and account access",
        "Sign in with your own account. Sessions expire after 8 hours; sign out when finished. "
        "Patients can access their own records. The clinic owner can review all patient records. "
        "Receptionists can access explicitly shared current doctor notes and prescriptions, not previous medical records. "
        "AI-generated explanations use the permitted source documents; check citations and ask the prescriber about unclear instructions. "
        "Document questions and relevant excerpts may be sent to OpenAI to generate an explanation. "
        "Keep private patient files out of the shared clinic-guide library.",
    ),
]

OTHER_BOOKINGS_PER_PATIENT = 3


def table_counts(db: Session) -> dict[str, int]:
    return {name: db.execute(text(f"SELECT count(*) FROM {name}")).scalar_one() for name in TABLES}


def _truncate(db: Session) -> None:
    db.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))


def _slots_for_day(day: date, doctor_id: int) -> list[m.Slot]:
    return slots_for_day(day, doctor_id)


def _weekdays(start: date, count: int) -> list[date]:
    return [d for d in (start + timedelta(days=i) for i in range(count)) if d.weekday() < 6]


def seed(db: Session, today: date | None = None) -> None:
    rng = random.Random(RANDOM_SEED)
    today = today or datetime.now(UTC).date()

    _truncate(db)

    clinic = m.Clinic(
        name="Terra Family Clinic",
        address="12 Terra Lane",
        phone="+1 555 0100",
        hours=HOURS,
    )
    db.add(clinic)
    db.flush()

    doctors = [
        m.Doctor(clinic_id=clinic.id, name=name, specialty=specialty, bio=bio) for name, specialty, bio in DOCTORS
    ]
    db.add_all(doctors)
    db.flush()

    users = [m.User(name=name, email=email, role=role) for name, email, role in USERS]
    db.add_all(users)
    db.flush()
    maya, others = users[0], users[3:]

    # Past 14 days (for seeded history) and next 14 days (bookable), weekdays only.
    past_days = _weekdays(today - timedelta(days=14), 14)
    future_days = _weekdays(today + timedelta(days=1), 14)
    slots: list[m.Slot] = []
    for doctor in doctors:
        for day in past_days + future_days:
            slots.extend(_slots_for_day(day, doctor.id))
    db.add_all(slots)
    db.flush()

    past_slots = [s for s in slots if s.starts_at.date() < today]
    future_slots = [s for s in slots if s.starts_at.date() > today]
    family_medicine = doctors[0].id
    fm_future = [s for s in future_slots if s.doctor_id == family_medicine]
    fm_past = [s for s in past_slots if s.doctor_id == family_medicine]

    def appointment(patient: m.User, slot: m.Slot, status: str, reason: str) -> m.Appointment:
        created = slot.starts_at - timedelta(days=rng.randint(2, 20))
        return m.Appointment(
            patient_id=patient.id,
            slot_id=slot.id,
            status=status,
            reason=reason,
            created_at=created,
            updated_at=created,
        )

    used_slot_ids: set[int] = set()
    appointments: list[m.Appointment] = []

    # Maya: 2 booked future, 2 completed past, 1 cancelled past.
    for slot, reason in zip(rng.sample(fm_future, 2), ["Annual check-up", "Blood pressure follow-up"], strict=True):
        appointments.append(appointment(maya, slot, "booked", reason))
        used_slot_ids.add(slot.id)
    for slot, reason in zip(
        rng.sample(fm_past, 2), ["Seasonal flu symptoms", "Medicine review"], strict=True
    ):
        appointments.append(appointment(maya, slot, "completed", reason))
        used_slot_ids.add(slot.id)
    cancelled_slot = rng.choice([s for s in fm_past if s.id not in used_slot_ids])
    appointments.append(appointment(maya, cancelled_slot, "cancelled", "Back pain"))
    used_slot_ids.add(cancelled_slot.id)

    # Other patients: booked future appointments with other doctors.
    for patient in others:
        pool = [s for s in future_slots if s.id not in used_slot_ids]
        for slot in rng.sample(pool, OTHER_BOOKINGS_PER_PATIENT):
            appointments.append(appointment(patient, slot, "booked", "General consultation"))
            used_slot_ids.add(slot.id)
    db.add_all(appointments)

    db.add_all([m.ClinicGuide(slug=slug, title=title, body=body) for slug, title, body in GUIDES])

    counts = []
    for offset in range(1, 61):  # 60 days ending yesterday
        day = today - timedelta(days=offset)
        if day.weekday() < 5:
            booked = rng.randint(18, 34)
        elif day.weekday() == 5:
            booked = rng.randint(6, 12)
        else:
            booked = rng.randint(0, 3)
        counts.append(
            m.DailyCount(
                day=day,
                booked=booked,
                completed=round(booked * 0.80),
                cancelled=round(booked * 0.10),
                no_show=round(booked * 0.06),
            )
        )
    db.add_all(counts)

    db.commit()


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as session:
        seed(session)
        for name, count in table_counts(session).items():
            print(f"{name}: {count}")
