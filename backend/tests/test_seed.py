from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Appointment, DailyCount, Doctor, Slot, User
from app.seed import seed, table_counts


def test_seed_twice_keeps_counts_unchanged(db: Session) -> None:
    before = table_counts(db)

    seed(db)

    assert table_counts(db) == before


def test_exactly_six_doctors_with_distinct_specialties(db: Session) -> None:
    specialties = db.scalars(select(Doctor.specialty)).all()

    assert len(specialties) == 6
    assert len(set(specialties)) == 6


def test_three_demo_roles_exist(db: Session) -> None:
    roles = set(db.scalars(select(User.role)).all())

    assert {"patient", "receptionist", "admin"} <= roles


def test_sixty_daily_counts_end_yesterday(db: Session) -> None:
    days = db.scalars(select(DailyCount.day).order_by(DailyCount.day)).all()
    yesterday = datetime.now(UTC).date() - timedelta(days=1)

    assert len(days) == 60
    assert days[-1] == yesterday
    assert days[0] == yesterday - timedelta(days=59)


def _free_slot_id(db: Session) -> int:
    booked_slot = (
        select(Appointment.slot_id)
        .where(Appointment.status == "booked")
        .scalar_subquery()
    )
    return db.scalar(select(Slot.id).where(Slot.id.not_in(booked_slot)).order_by(Slot.id).limit(1))


def test_partial_unique_index_rejects_two_booked_for_one_slot(db: Session) -> None:
    slot_id = _free_slot_id(db)
    patient_id = db.scalar(select(User.id).where(User.role == "patient").order_by(User.id).limit(1))
    now = datetime.now(UTC)
    db.add_all(
        [
            Appointment(patient_id=patient_id, slot_id=slot_id, status="booked", reason="a", created_at=now, updated_at=now),
            Appointment(patient_id=patient_id, slot_id=slot_id, status="booked", reason="b", created_at=now, updated_at=now),
        ]
    )

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_partial_unique_index_allows_booked_plus_cancelled_for_one_slot(db: Session) -> None:
    slot_id = _free_slot_id(db)
    patient_id = db.scalar(select(User.id).where(User.role == "patient").order_by(User.id).limit(1))
    now = datetime.now(UTC)
    db.add_all(
        [
            Appointment(patient_id=patient_id, slot_id=slot_id, status="booked", reason="a", created_at=now, updated_at=now),
            Appointment(patient_id=patient_id, slot_id=slot_id, status="cancelled", reason="b", created_at=now, updated_at=now),
        ]
    )

    db.flush()
    db.rollback()


def test_seed_is_deterministic_for_fixed_day(db: Session) -> None:
    day = date(2030, 1, 7)
    seed(db, today=day)
    first = db.scalars(select(Appointment.reason).order_by(Appointment.id)).all()

    seed(db, today=day)
    second = db.scalars(select(Appointment.reason).order_by(Appointment.id)).all()

    assert first == second
