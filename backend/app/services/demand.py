"""Seven-day demand inference. Training is explicit; requests only read JSON coefficients."""

import json
import logging
import math
from datetime import date, timedelta
from pathlib import Path
from app.clinic import bounds

ARTIFACT = Path(__file__).resolve().parents[2] / "data" / "demand-demo-v1.json"
FEATURES = [*[f"weekday_{i}" for i in range(6)], "open_day_trend_years", "last_same_weekday", "mean_four_same_weekdays"]
MIN_HISTORY = 56
logger = logging.getLogger(__name__)


def features(history: list[dict], target: date, epoch: date) -> list[float]:
    """history is an origin-frozen prefix, never extended with future actuals."""
    recent = [r["demand"] for r in history if date.fromisoformat(r["day"]).weekday() == target.weekday()][-4:]
    return [
        *[float(target.weekday() == i) for i in range(6)],
        (target - epoch).days / 365 if target.weekday() < 6 else 0.0,
        float(recent[-1]) if recent else 0.0,
        sum(recent) / len(recent) if recent else 0.0,
    ]


def baseline(history: list[dict], target: date) -> float:
    recent = [r["demand"] for r in history if date.fromisoformat(r["day"]).weekday() == target.weekday()][-4:]
    return sum(recent) / len(recent) if recent else 0.0


def raw_prediction(history: list[dict], target: date, model: dict | None = None) -> float:
    if model is None:
        return baseline(history, target)
    values = features(history, target, date.fromisoformat(model["epoch"]))
    return model["intercept"] + sum(c * x for c, x in zip(model["coefficients"], values, strict=True))


def predict(history: list[dict], target: date, capacity: int, model: dict | None = None) -> float:
    if capacity <= 0:
        return 0.0
    raw = raw_prediction(history, target, model)
    return round(min(capacity, max(0.0, raw)), 1)


def demo_forecast(today: date) -> dict:
    try:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        if artifact["schema_version"] != 1 or artifact["features"] != FEATURES:
            raise ValueError("Unsupported demand model features")
        model = artifact["model"]
        if len(model["coefficients"]) != len(FEATURES) or not all(
            math.isfinite(v) for v in [model["intercept"], *model["coefficients"]]
        ):
            raise ValueError("Invalid model coefficients")
        history = artifact["history"]
        trained_until = date.fromisoformat(history[-1]["day"])
        date.fromisoformat(model["epoch"])
        if trained_until >= today:
            return {"status": "unavailable", "message": "Training data extends beyond the current date. Refresh the forecast model."}
        if (today - trained_until).days > 7:
            return {"status": "stale", "message": "Forecast model is older than seven days. Run the training command to refresh it."}
        selected = artifact["selected_method"]
        points = []
        for offset in range(1, 8):
            day = today + timedelta(days=offset)
            hours = bounds(day)
            capacity = (hours[1] - hours[0]) * 2 * 6 if hours else 0
            points.append({
                "day": day.isoformat(), "capacity": capacity,
                "predicted_booked": predict(history, day, capacity, model if selected == "linear_regression" else None),
                "linear_regression": predict(history, day, capacity, model),
                "baseline": predict(history, day, capacity),
            })
        return {
            "status": "ready", "source": "Generated appointment history, separate from current bookings",
            "selected_method": selected, "trained_at": artifact["trained_at"],
            "training_start": history[0]["day"], "training_end": history[-1]["day"],
            "training_days": len(history), "dataset_id": artifact["dataset_id"],
            "metrics": artifact["metrics"], "features": FEATURES, "points": points,
            "history": history[-30:], "versions": artifact["versions"],
            "comparisons": artifact.get("comparisons", []),
        }
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        logger.warning("Demand model artifact unavailable or invalid", exc_info=True)
        return {"status": "unavailable", "message": "Forecast model unavailable. Current activity and its baseline remain available."}
