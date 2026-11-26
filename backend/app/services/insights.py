from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.clinic import valid_slot
from app.models import Appointment, Slot
from app.services.demand import MIN_HISTORY, demo_forecast, predict

HISTORY_DAYS = 30
FORECAST_DAYS = 7
FORECAST_WEEKS = 4
FORECAST_LABEL = "Live baseline forecast"
FORECAST_METHOD = "Mean of up to four observed matching weekdays; bounded by published slot capacity and confirmed bookings"


def forecast(history_by_day: dict[date, int], start: date, days: int = FORECAST_DAYS) -> list[tuple[date, float]]:
    points: list[tuple[date, float]] = []
    for offset in range(days):
        target = start + timedelta(days=offset)
        prior = sorted((d for d in history_by_day if d < target and d.weekday() == target.weekday()), reverse=True)
        recent = prior[:FORECAST_WEEKS]
        value = sum(history_by_day[d] for d in recent) / len(recent) if recent else 0.0
        points.append((target, round(value, 1)))
    return points


def _rate(part: int, booked: int) -> float:
    return round(part / booked, 3) if booked else 0.0


def build_insights(db: Session, today: date | None = None) -> dict:
    timezone = get_settings().clinic_timezone
    today = today or datetime.now(ZoneInfo(timezone)).date()
    local_day = func.date(func.timezone(timezone, Slot.starts_at))
    capacities = {}
    for slot in db.scalars(select(Slot)):
        if valid_slot(slot):
            day = slot.starts_at.astimezone(ZoneInfo(timezone)).date()
            capacities[day] = capacities.get(day, 0) + 1
    counts = {}
    for day, status, count in db.execute(
        select(local_day, Appointment.status, func.count(Appointment.id))
        .join(Slot, Appointment.slot_id == Slot.id).group_by(local_day, Appointment.status)
    ):
        counts.setdefault(day, {})[status] = count
    history = []
    for offset in range(HISTORY_DAYS, 0, -1):
        day = today - timedelta(days=offset)
        statuses = counts.get(day, {})
        history.append({
            "day": day.isoformat(), "booked": sum(statuses.values()),
            "completed": statuses.get("completed", 0), "cancelled": statuses.get("cancelled", 0),
            "no_show": statuses.get("no_show", 0), "capacity": capacities.get(day, 0),
            "data_status": "observed" if day in capacities or day in counts else "no_schedule",
        })
    totals = {key: sum(row[key] for row in history) for key in ("booked", "completed", "cancelled", "no_show")}
    for name, part in (("cancellation_rate", "cancelled"), ("no_show_rate", "no_show")):
        totals[name] = _rate(totals[part], totals["booked"])
    known = []
    for day in sorted(set(capacities) | set(counts)):
        if day >= today:
            continue
        statuses = counts.get(day, {})
        known.append({"day": day.isoformat(), "demand": sum(n for status, n in statuses.items() if status != "cancelled")})
    points = []
    for offset in range(1, FORECAST_DAYS + 1):
        day = today + timedelta(days=offset)
        capacity = capacities.get(day, 0)
        confirmed = counts.get(day, {}).get("booked", 0)
        matching = [r for r in known if date.fromisoformat(r["day"]).weekday() == day.weekday()]
        estimate = max(float(confirmed), predict(known, day, capacity)) if capacity and matching else None
        points.append({
            "day": day.isoformat(), "predicted_booked": estimate, "confirmed": confirmed,
            "capacity": capacity, "remaining_capacity": round(max(0, capacity - estimate), 1) if estimate is not None else None,
            "utilisation": round(estimate / capacity, 3) if capacity and estimate is not None else None,
            "schedule_status": "published" if capacity else "no_schedule",
            "estimate_status": "ready" if estimate is not None else "insufficient_history" if capacity else "no_schedule",
        })
    span = (today - date.fromisoformat(known[0]["day"])).days if known else 0
    published = [p for p in points if p["predicted_booked"] is not None]
    total_capacity = sum(p["capacity"] for p in points)
    complete = all(p["predicted_booked"] is not None for p in points if p["capacity"])
    predicted = round(sum(p["predicted_booked"] for p in published), 1)
    return {
        "totals": totals, "window_days": HISTORY_DAYS, "history": history,
        "source": "Current appointment records", "timezone": timezone,
        "history_note": "Scheduled-date totals reflect current records. Earlier reschedules cannot be reconstructed before event tracking began. No schedule does not mean closed.",
        "forecast": {
            "label": FORECAST_LABEL, "method": FORECAST_METHOD, "points": points,
            "status": "limited_history" if span < MIN_HISTORY else "baseline",
            "message": "Current records use a weekday baseline. The workload model below uses a separate training dataset.",
            "observed_days": len(known), "history_span_days": span,
        },
        "business": {"expected_visits": predicted if complete and total_capacity else None, "confirmed_visits": sum(p["confirmed"] for p in points),
                     "capacity": total_capacity, "published_days": sum(bool(p["capacity"]) for p in points),
                     "utilisation": round(predicted / total_capacity, 3) if total_capacity and complete else None,
                     "remaining_capacity": round(max(0, total_capacity - predicted), 1) if complete and total_capacity else None},
        "model_demo": demo_forecast(today),
    }
