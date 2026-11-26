"""Refresh clinic presentation without reseeding accounts, slots or appointments."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AssistantAction, ClinicGuide, Doctor

DOCTOR_RENAMES = {
    "Dr. Lena Ortiz": "Dr. Ananya Sharma",
    "Dr. Marco Bell": "Dr. Arjun Mehta",
    "Dr. Hana Kim": "Dr. Kavya Rao",
    "Dr. Owen Walsh": "Dr. Rohan Iyer",
    "Dr. Ruth Adeyemi": "Dr. Nisha Verma",
    "Dr. Ines Costa": "Dr. Meera Kapoor",
}


def main():
    with SessionLocal.begin() as db:
        renamed = 0
        for old, new in DOCTOR_RENAMES.items():
            rows = db.scalars(select(Doctor).where(Doctor.name.in_((old, new)))).all()
            if len(rows) != 1:
                raise ValueError(f"Expected exactly one configured doctor for {new}; no changes committed.")
            rows[0].name = new
            renamed += 1
        for guide in db.scalars(select(ClinicGuide)):
            guide.body = guide.body.replace("hours (IST):", "hours:").replace("All published times use IST.", "").strip()
        for action in db.scalars(select(AssistantAction).where(AssistantAction.status == "pending")):
            for old, new in DOCTOR_RENAMES.items():
                action.summary = action.summary.replace(old, new)
            action.summary = action.summary.replace(" IST", "")
    print(f"Updated {renamed} doctor display names and clinic labels; IDs and bookings preserved.")


if __name__ == "__main__":
    main()
