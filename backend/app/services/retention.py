"""Return probabilities from a synthetic demonstration model; never clinical advice."""
import json
import math
from datetime import timedelta, date
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parents[2] / "data" / "retention-demo-v1.json"
FEATURES = ["days_since_completed", "completed_90", "completed_180", "mean_gap", "cancelled_180", "no_show_180"]


def patient_features(events, as_of):
    past = sorted((e for e in events if e["day"] < as_of), key=lambda e: e["day"])
    done = [e["day"] for e in past if e["status"] == "completed"]
    if not done:
        return None
    recent = [e for e in past if e["day"] >= as_of - timedelta(days=180)]
    gaps = [(b - a).days for a, b in zip(done, done[1:])]
    return [float((as_of - done[-1]).days), sum(d >= as_of - timedelta(days=90) for d in done),
            sum(e["status"] == "completed" for e in recent), sum(gaps) / len(gaps) if gaps else 180.0,
            sum(e["status"] == "cancelled" for e in recent), sum(e["status"] == "no_show" for e in recent)]


def probability(values, artifact):
    model = artifact["model"]
    if artifact["features"] != FEATURES or any(len(model[k]) != len(FEATURES) for k in ("mean", "scale", "coefficients")):
        raise ValueError("Unsupported retention model")
    score = model["intercept"] + sum(c * (x - m) / s for x, m, s, c in
             zip(values, model["mean"], model["scale"], model["coefficients"], strict=True))
    if not math.isfinite(score):
        raise ValueError("Nonfinite retention probability")
    score = model.get("calibration_slope", 1.0) * score + model.get("calibration_intercept", 0.0)
    return round(1 / (1 + math.exp(-max(-700, min(700, score)))), 3)


def load_model(today):
    try:
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        end = date.fromisoformat(artifact["observation_end"])
        if end > today or (today - end).days > 30:
            return None
        probability([30, 2, 4, 45, 0, 0], artifact)
        return artifact
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError):
        return None
