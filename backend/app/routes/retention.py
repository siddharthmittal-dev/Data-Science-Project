from datetime import datetime, UTC
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_admin
from app.models import Appointment, FollowUpTask, Slot, User
from app.services.retention import load_model, patient_features, probability

router = APIRouter(prefix="/retention", tags=["retention"])


@router.get("")
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    zone = ZoneInfo(get_settings().clinic_timezone)
    now = datetime.now(UTC)
    today = now.astimezone(zone).date()
    model = load_model(today)
    visits = db.execute(select(Appointment, Slot).join(Slot, Appointment.slot_id == Slot.id)).all()
    tasks = db.scalars(select(FollowUpTask).order_by(FollowUpTask.created_at.desc())).all()
    patients = []
    for patient in db.scalars(select(User).where(User.role == "patient").order_by(User.name)):
        rows = [(a, s) for a, s in visits if a.patient_id == patient.id]
        events = [{"day": s.starts_at.astimezone(zone).date(), "status": a.status} for a, s in rows]
        values = patient_features(events, today)
        upcoming = [s.starts_at for a, s in rows if a.status == "booked" and s.starts_at > now]
        score = None
        if values is not None and model:
            score = probability(values, model) if model["selected_method"] == "logistic" else round(model["baseline_probability"], 3)
        done = [s.starts_at for a, s in rows if a.status == "completed" and s.starts_at < now]
        patients.append({"id": patient.id, "name": patient.name, "return_probability": score,
                         "days_since_completed": int(values[0]) if values else None,
                         "last_completed": max(done) if done else None, "completed_visits": len(done),
                         "next_booking": min(upcoming) if upcoming else None,
                         "open_task": next((t.id for t in tasks if t.patient_id == patient.id and t.status == "open"), None),
                         "review_eligible": values is not None and not upcoming,
                         "reason": "Already booked" if upcoming else "No completed history" if values is None else "Available for staff review"})
    names = {p["id"]: p["name"] for p in patients}
    task_rows = [{"id": t.id, "patient_id": t.patient_id, "patient_name": names.get(t.patient_id, "Patient"),
                  "note": t.note, "status": t.status, "outcome": t.outcome, "created_at": t.created_at,
                  "completed_at": t.completed_at,
                  "subsequent_return": any(a.patient_id == t.patient_id and a.status == "completed" and s.starts_at > t.created_at for a, s in visits)} for t in tasks]
    return {"patients": sorted(patients, key=lambda p: (not p["review_eligible"], p["return_probability"] is None, p["return_probability"] or 0)),
            "tasks": task_rows, "model": {k: model[k] for k in ("source", "selected_method", "population", "trained_at", "training_samples", "training_label_end", "validation_origin", "holdout_origin", "metrics", "examples")} if model else None,
            "notice": "Estimates support staff review. Returning is not a medical requirement. Follow-up tasks are internal; no messages are sent. See model details for the training data and evaluation scope."}


class TaskIn(BaseModel):
    patient_id: int
    note: str = Field(min_length=1, max_length=500)


class CompleteIn(BaseModel):
    outcome: str = Field(min_length=1, max_length=500)


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    patient = db.scalar(select(User).where(User.id == body.patient_id, User.role == "patient").with_for_update())
    if patient is None:
        raise HTTPException(404, detail={"code": "patient_not_found", "message": "Choose an existing patient."})
    if not body.note.strip():
        raise HTTPException(422, detail={"code": "validation_error", "message": "Enter a follow-up note."})
    if db.scalar(select(FollowUpTask.id).where(FollowUpTask.patient_id == patient.id, FollowUpTask.status == "open")):
        raise HTTPException(409, detail={"code": "task_exists", "message": "This patient already has an open task."})
    task = FollowUpTask(patient_id=patient.id, created_by=user.id, note=body.note.strip())
    db.add(task)
    db.commit()
    return {"id": task.id, "status": task.status}


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, body: CompleteIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    task = db.scalar(select(FollowUpTask).where(FollowUpTask.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(404, detail={"code": "task_not_found", "message": "That task does not exist."})
    if task.status != "open":
        raise HTTPException(409, detail={"code": "task_completed", "message": "This task is already complete."})
    if not body.outcome.strip():
        raise HTTPException(422, detail={"code": "validation_error", "message": "Record the follow-up outcome."})
    task.status = "completed"
    task.outcome = body.outcome.strip()
    task.completed_at = datetime.now(UTC)
    db.commit()
    return {"id": task.id, "status": task.status}
