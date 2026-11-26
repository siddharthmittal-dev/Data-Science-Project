"""Explicit, deterministic synthetic training. Never connects to or seeds PostgreSQL.

Run from backend: ../.venv/Scripts/python.exe -m app.train_demand
Only the compact, versioned JSON artifact is written; no pickle or temporary files.
"""

import argparse
import hashlib
import json
import math
import random
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import sklearn
from sklearn.linear_model import LinearRegression

from app.services.demand import ARTIFACT, FEATURES, features, predict, raw_prediction
from app.config import get_settings
from app.clinic import bounds

SEED = 42


def synthetic_history(end: date, days: int = 365, scenario: str = "growth") -> list[dict]:
    """Aggregate fictional visit outcomes without creating patients in the app DB."""
    rng = random.Random(SEED)
    rows = []
    for index in range(days):
        day = end - timedelta(days=days - 1 - index)
        hours = bounds(day)
        capacity = (hours[1] - hours[0]) * 2 * 6 if hours else 0
        if scenario == "closures" and index % 90 == 0:
            capacity = 0
        trend = index * (-0.045 if scenario == "decline" else 0 if scenario == "flat" else 0.065)
        shock = 25 if scenario == "sudden_change" and index >= 300 else 0
        count = min(capacity, max(0, round(
            [46, 52, 49, 58, 62, 24, 0][day.weekday()] + trend + shock + rng.gauss(0, 3)
        ))) if capacity else 0
        outcomes = {"completed": 0, "cancelled": 0, "no_show": 0}
        for _ in range(count):
            outcome = rng.choices(["completed", "cancelled", "no_show"], weights=[85, 10, 5])[0]
            outcomes[outcome] += 1
        rows.append({"day": day.isoformat(), "capacity": capacity, "booked": count,
                     **outcomes, "demand": count - outcomes["cancelled"]})
    return rows


def fit(history: list[dict]) -> dict:
    epoch = date.fromisoformat(history[0]["day"])
    # Each training example mimics its horizon at an origin with a one-day
    # reporting delay: today's complete count is not yet available.
    x, y = [], []
    for origin in range(56, len(history) - 7, 7):
        known = history[:origin]
        for horizon in range(1, 8):
            row = history[origin + horizon]
            x.append(features(known, date.fromisoformat(row["day"]), epoch))
            y.append(row["demand"])
    if not x:
        raise ValueError("At least 65 complete days required to train")
    estimator = LinearRegression().fit(x, y)
    return {"epoch": epoch.isoformat(), "intercept": float(estimator.intercept_),
            "coefficients": estimator.coef_.tolist()}


def evaluate(rows: list[dict], start: int, stop: int) -> dict:
    errors = {name: [[] for _ in range(7)] for name in ("linear_regression", "baseline")}
    constraints = {name: {"negative_raw": 0, "above_capacity_raw": 0, "open_day_predictions": 0} for name in errors}
    for origin in range(start, stop - 7):
        known = rows[:origin]
        model = fit(known)
        for horizon in range(1, 8):
            row = rows[origin + horizon]
            for name in errors:
                if row["capacity"]:
                    raw = raw_prediction(known, date.fromisoformat(row["day"]), model if name == "linear_regression" else None)
                    constraints[name]["negative_raw"] += int(raw < 0)
                    constraints[name]["above_capacity_raw"] += int(raw > row["capacity"])
                    constraints[name]["open_day_predictions"] += 1
                value = predict(known, date.fromisoformat(row["day"]), row["capacity"],
                                model if name == "linear_regression" else None)
                errors[name][horizon - 1].append(value - row["demand"])
    result = {}
    for name, by_horizon in errors.items():
        flat = [error for values in by_horizon for error in values]
        result[name] = {"mae": round(sum(abs(e) for e in flat) / len(flat), 3),
                        "rmse": round(math.sqrt(sum(e * e for e in flat) / len(flat)), 3),
                        "samples": len(flat), **constraints[name],
                        "mae_by_horizon": [round(sum(abs(e) for e in values) / len(values), 3)
                                           for values in by_horizon]}
        open_errors = []
        for horizon, values in enumerate(by_horizon, start=1):
            for origin, error in zip(range(start, stop - 7), values, strict=True):
                if rows[origin + horizon]["capacity"]:
                    open_errors.append(error)
        result[name]["mae_open_days"] = round(sum(abs(e) for e in open_errors) / len(open_errors), 3) if open_errors else None
    return result


def train(end: date, scenario: str = "growth") -> dict:
    rows = synthetic_history(end, scenario=scenario)
    # Selection uses an earlier validation window only. Holdout is never used
    # to choose the method. Rolling holdout refits use only then-known outcomes.
    validation = evaluate(rows, len(rows) - 112, len(rows) - 56)
    holdout = evaluate(rows, len(rows) - 56, len(rows))
    selected = "linear_regression" if validation["linear_regression"]["mae"] < validation["baseline"]["mae"] else "baseline"
    dataset_id = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:16]
    return {"schema_version": 1, "dataset_id": dataset_id, "seed": SEED, "scenario": scenario,
            "trained_at": datetime.now(UTC).isoformat(), "features": FEATURES,
            "versions": {"scikit_learn": sklearn.__version__, "numpy": np.__version__},
            "target": "Daily non-cancelled scheduled visits (completed plus no-show)",
            "source": "synthetic", "model": fit(rows), "selected_method": selected,
            "metrics": {"validation": validation, "holdout": holdout,
                        "selection_basis": "Lowest validation MAE; holdout not used for selection",
                        "holdout_start": rows[-55]["day"], "holdout_end": rows[-1]["day"],
                        "protocol": "Daily rolling origins, seven horizons, one-day reporting delay; clipped to capacity"},
            "history": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo(get_settings().clinic_timezone)).date() - timedelta(days=1))
    args = parser.parse_args()
    artifact = train(args.end)
    artifact["comparisons"] = [{"scenario": name, "selected_method": result["selected_method"], "holdout": result["metrics"]["holdout"]}
                               for name in ("flat", "decline", "closures", "sudden_change")
                               if (result := train(args.end, scenario=name))]
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(ARTIFACT), "selected": artifact["selected_method"],
                      "holdout": artifact["metrics"]["holdout"]}, indent=2))
