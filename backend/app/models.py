from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLES = ("patient", "receptionist", "admin")
APPOINTMENT_STATUSES = ("booked", "cancelled", "completed", "no_show")
ACTION_STATUSES = ("pending", "confirmed", "dismissed", "failed")


def _in_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300))
    phone: Mapped[str] = mapped_column(String(40))
    hours: Mapped[str] = mapped_column(String(300))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(256))

    __table_args__ = (
        CheckConstraint(_in_check("role", ROLES), name="ck_users_role"),
        Index("uq_registered_role", "role", unique=True,
              postgresql_where=text("password_hash IS NOT NULL")),
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"))
    name: Mapped[str] = mapped_column(String(200))
    specialty: Mapped[str] = mapped_column(String(200))
    bio: Mapped[str] = mapped_column(Text)


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("doctor_id", "starts_at", name="uq_slots_doctor_starts_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(_in_check("status", APPOINTMENT_STATUSES), name="ck_appointments_status"),
        # Double-booking guard: at most one booked appointment per slot, enforced by the database.
        Index(
            "uq_appointments_slot_booked",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppointmentEvent(Base):
    __tablename__ = "appointment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    previous_slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id"))
    status: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BookingRequest(Base):
    __tablename__ = "booking_requests"
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    signature: Mapped[str] = mapped_column(String(64))
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"))


class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(String(500))
    outcome: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClinicGuide(Base):
    __tablename__ = "clinic_guides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)


class DailyCount(Base):
    __tablename__ = "daily_counts"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    booked: Mapped[int] = mapped_column(Integer)
    completed: Mapped[int] = mapped_column(Integer)
    cancelled: Mapped[int] = mapped_column(Integer)
    no_show: Mapped[int] = mapped_column(Integer)


class AssistantAction(Base):
    __tablename__ = "assistant_actions"
    __table_args__ = (CheckConstraint(_in_check("status", ACTION_STATUSES), name="ck_assistant_actions_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict] = mapped_column(JSONB)
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
