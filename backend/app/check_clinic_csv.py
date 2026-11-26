"""Validate delivered clinic CSVs and backtest against chronological baselines."""

import argparse
import csv
import hashlib
import json
import calendar as month_calendar
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (brier_score_loss, mean_absolute_error, roc_auc_score, roc_curve,
                             precision_recall_curve, average_precision_score, confusion_matrix,
                             precision_score, recall_score, f1_score, r2_score, mean_squared_error)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load(directory):
    rows = read_csv(directory / "appointments.csv")
    calendar = read_csv(directory / "clinic_calendar.csv")
    if not rows or not calendar:
        raise ValueError("Both CSVs must contain data.")
    appointments = []
    seen = set()
    slots = defaultdict(list)
    counts = Counter()
    specialties = {}
    days = {}
    for row in calendar:
        day = date.fromisoformat(row["date"])
        capacity, opened = int(row["available_slots"]), int(row["is_open"])
        if day in days or capacity < 0 or opened not in (0, 1):
            raise ValueError(f"Invalid or duplicate calendar date {day}.")
        if (not opened and capacity) or (day.weekday() == 6 and opened):
            raise ValueError(f"Invalid closed-day capacity {day}.")
        if not opened and not row["closure_reason"].strip():
            raise ValueError(f"Missing closure reason {day}.")
        days[day] = capacity
    if len(days) != (max(days) - min(days)).days + 1:
        raise ValueError("Calendar dates have gaps.")
    for row in rows:
        item = dict(row)
        for key in ("booked_at", "scheduled_start", "scheduled_end", "status_recorded_at", "cancelled_at", "reminder_sent_at"):
            item[key] = datetime.fromisoformat(row[key]) if row[key] else None
            if item[key] is not None and item[key].utcoffset() != timedelta(hours=5, minutes=30):
                raise ValueError(f"Timestamp must use the +05:30 offset in {row['appointment_id']}.")
        start, end, booked, recorded = (item[k] for k in ("scheduled_start", "scheduled_end", "booked_at", "status_recorded_at"))
        if not all((start, end, booked, recorded)) or not booked < start or end - start != timedelta(minutes=30):
            raise ValueError(f"Invalid appointment timestamps {row['appointment_id']}.")
        opening, closing = (time(9), time(13)) if start.weekday() == 5 else (time(8), time(18))
        if start.weekday() == 6 or start.date() != end.date() or not opening <= start.time() < end.time() <= closing:
            raise ValueError(f"Appointment outside clinic hours {row['appointment_id']}.")
        if start.date() not in days or days[start.date()] <= 0:
            raise ValueError("Appointment falls on a closed or missing calendar day.")
        if not all(row[k].strip() for k in ("appointment_id", "patient_id", "doctor_id", "specialty")) or row["appointment_id"] in seen:
            raise ValueError("Missing identifier or duplicate appointment ID.")
        seen.add(row["appointment_id"])
        doctor = row["doctor_id"]
        if doctor in specialties and specialties[doctor] != row["specialty"]:
            raise ValueError("Doctor specialty changes between records.")
        specialties[doctor] = row["specialty"]
        cancelled = item["cancelled_at"]
        if row["status"] == "cancelled":
            if not cancelled or not booked <= cancelled < start or cancelled != recorded:
                raise ValueError("Invalid cancellation timestamps.")
        elif row["status"] in ("completed", "no_show"):
            if cancelled or recorded < end:
                raise ValueError("Invalid outcome timestamp.")
            counts[start.date()] += 1
            slots[doctor].append((start, end))
        else:
            raise ValueError("Unknown appointment status.")
        reminder = item["reminder_sent_at"]
        if reminder and (not booked < reminder < start or (cancelled and reminder >= cancelled)):
            raise ValueError("Invalid reminder timestamp.")
        if row["booking_channel"] not in ("phone", "walk_in", "online") or row["visit_type"] not in ("initial", "follow_up"):
            raise ValueError("Unknown booking channel or visit type.")
        appointments.append(item)
    for events in slots.values():
        events.sort()
        if any(current[0] < previous[1] for previous, current in zip(events, events[1:])):
            raise ValueError("Doctor appointment overlap.")
    if any(count > days[day] for day, count in counts.items()):
        raise ValueError("Appointments exceed published capacity.")
    return sorted(appointments, key=lambda r: r["scheduled_start"]), days


def bootstrap_uncertainty(train_x, outcomes, future_x, capacities, draws=400, seed=42):
    """Conditional residual bootstrap with weekday-aligned seven-day blocks."""
    x = np.column_stack([np.ones(len(train_x)), train_x])
    future = np.column_stack([np.ones(len(future_x)), future_x])
    inverse = np.linalg.pinv(x)
    fitted = x @ (inverse @ outcomes)
    residuals = np.asarray(outcomes) - fitted
    residuals -= residuals.mean()
    rng = np.random.default_rng(seed)
    starts = np.arange(0, len(x) - 6, 7)
    if not len(starts):
        raise ValueError("At least seven training days are required for block intervals.")
    coefficients, means, predictions = [], [], []
    for _ in range(draws):
        blocks = rng.choice(starts, size=int(np.ceil((len(x) + len(future)) / 7)))
        noise = np.concatenate([residuals[start:start + 7] for start in blocks])
        beta = inverse @ (fitted + noise[:len(x)])
        raw = future @ beta
        coefficients.append(beta)
        means.append(np.clip(raw, 0, capacities))
        predictions.append(np.clip(raw + noise[len(x):len(x) + len(future)], 0, capacities))
    return {"level": 0.95, "draws": draws, "seed": seed, "block_days": 7,
            "method": "Weekday-aligned residual block bootstrap; fixed features; conditional on OLS and published capacity. Nominal 95% intervals are approximate, not coverage-validated.",
            "coefficient_intervals": np.quantile(coefficients, [0.025, 0.975], axis=0).T.tolist(),
            "mean_intervals": np.quantile(means, [0.025, 0.975], axis=0).T.tolist(),
            "prediction_intervals": np.quantile(predictions, [0.025, 0.975], axis=0).T.tolist(),
            "monthly_prediction_interval": np.quantile(np.sum(predictions, axis=1), [0.025, 0.975]).tolist()}


def count_backtest(rows, calendar, target):
    last_visit = max(r["scheduled_start"].date() for r in rows)
    last = last_visit.replace(day=month_calendar.monthrange(last_visit.year, last_visit.month)[1])
    counts = Counter(r["scheduled_start"].date() for r in rows if r["status"] == target)
    dates = [d for d in sorted(calendar) if d <= last]
    months = sorted({d.strftime("%Y-%m") for d in dates})
    if len(months) < 6:
        raise ValueError("Six complete observed months are required.")

    def features(day, history):
        prior = [counts[d] for d in history if d.weekday() == day.weekday()][-4:]
        return [float(day.weekday() == i) for i in range(6)] + [calendar[day], (day - dates[0]).days / 180,
                                                               float(np.mean(prior)) if prior else 0.0]

    def forecast(train, test):
        x = [features(d, [p for p in train if p < d]) for d in train]
        model = LinearRegression().fit(x, [counts[d] for d in train])
        linear = model.predict([features(d, train) for d in test])
        linear = [min(calendar[d], max(0.0, float(v))) if calendar[d] else 0.0 for d, v in zip(test, linear)]
        baseline = [min(calendar[d], features(d, train)[-1]) if calendar[d] else 0.0 for d in test]
        return {"linear_regression": linear, "weekday_baseline": baseline}, model, x

    scores = {}
    evaluation_points = {}
    for name, month in (("validation", months[-2]), ("holdout", months[-1])):
        test = [d for d in dates if d.strftime("%Y-%m") == month]
        train = [d for d in dates if d < test[0]]
        predictions, _, _ = forecast(train, test)
        scores[name] = {method: {"daily_mae": round(mean_absolute_error([counts[d] for d in test], values), 4),
                                 "rmse": float(np.sqrt(mean_squared_error([counts[d] for d in test], values))),
                                 "r2": float(r2_score([counts[d] for d in test], values)),
                                 "predicted_total": round(sum(values), 2), "actual_total": sum(counts[d] for d in test)}
                        for method, values in predictions.items()}
        evaluation_points[name] = [{"day": d.isoformat(), "actual": counts[d],
                                   **{method: float(values[i]) for method, values in predictions.items()}}
                                  for i, d in enumerate(test)]
    selected = min(scores["validation"], key=lambda method: scores["validation"][method]["daily_mae"])
    next_month = last + timedelta(days=1)
    next_month_end = next_month.replace(day=month_calendar.monthrange(next_month.year, next_month.month)[1])
    future = [d for d in sorted(calendar) if next_month <= d <= next_month_end]
    if len(future) != next_month_end.day:
        raise ValueError("A complete next-month calendar is required.")
    values, fitted, train_x = forecast(dates, future)
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
             "published_capacity", "days_since_start_divided_by_180", "mean_last_four_matching_weekdays"]
    rank = int(np.linalg.matrix_rank(np.column_stack([np.ones(len(train_x)), train_x])))
    uncertainty = bootstrap_uncertainty(train_x, [counts[d] for d in dates],
                                        [features(d, dates) for d in future], [calendar[d] for d in future])
    return {"target": target, "selected_method": selected, "validation_month": months[-2], "holdout_month": months[-1],
            "metrics": scores, "forecast_month": future[0].strftime("%Y-%m") if future else None,
            "forecast_total": round(sum(values[selected]), 2) if future else None,
            "evaluation_points": evaluation_points, "uncertainty": uncertainty,
            "model": {"intercept": float(fitted.intercept_), "coefficients": fitted.coef_.tolist(), "features": names,
                      "training_days": len(dates), "training_start": dates[0].isoformat(), "training_end": dates[-1].isoformat(),
                      "design_rank": rank, "design_columns": len(names) + 1,
                      "training_rmse_raw": float(np.sqrt(mean_squared_error([counts[d] for d in dates], fitted.predict(train_x))))},
            "points": [{"day": d.isoformat(), "predicted": float(values[selected][i]),
                        "regression": float(values["linear_regression"][i]), "baseline": float(values["weekday_baseline"][i]),
                        "capacity": calendar[d], "features": features(d, dates),
                        "raw": float(fitted.predict([features(d, dates)])[0])} for i, d in enumerate(future)]}


def no_show_backtest(rows):
    examples = []
    for row in rows:
        if row["status"] == "cancelled":
            continue
        cutoff = row["booked_at"]
        history = [r for r in rows if r["patient_id"] == row["patient_id"] and r["status_recorded_at"] < cutoff]
        done = [r["scheduled_start"] for r in history if r["status"] == "completed"]
        features = [(row["scheduled_start"] - cutoff).total_seconds() / 86400,
                    sum(r["status"] == "completed" for r in history), sum(r["status"] == "no_show" for r in history),
                    sum(r["status"] == "cancelled" for r in history),
                    (cutoff - max(done)).total_seconds() / 86400 if done else 180,
                    *[float(row["scheduled_start"].weekday() == i) for i in range(6)]]
        examples.append((row, features, int(row["status"] == "no_show")))
    months = sorted({r["scheduled_start"].strftime("%Y-%m") for r in rows})
    results = {}
    for phase, month in (("validation", months[-2]), ("holdout", months[-1])):
        test = [e for e in examples if e[0]["scheduled_start"].strftime("%Y-%m") == month]
        origin = datetime.fromisoformat(month + "-01T00:00:00+05:30")
        train = [e for e in examples if e[0]["status_recorded_at"] < origin]
        if len({e[2] for e in train}) < 2 or not test:
            return {"status": "insufficient_class_support"}
        estimator = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
        estimator.fit([e[1] for e in train], [e[2] for e in train])
        predicted = estimator.predict_proba([e[1] for e in test])[:, 1]
        actual = [e[2] for e in test]
        fpr, tpr, thresholds = roc_curve(actual, predicted)
        precision, recall, _ = precision_recall_curve(actual, predicted)
        classes = predicted >= 0.5
        calibration = []
        for lo in np.arange(0, 1, 0.2):
            chosen = (predicted >= lo) & (predicted < lo + 0.2 if lo < 0.8 else predicted <= 1)
            if chosen.any():
                calibration.append({"predicted": float(np.mean(predicted[chosen])),
                                    "observed": float(np.mean(np.array(actual)[chosen])), "count": int(chosen.sum())})
        scaler, classifier = estimator.steps[0][1], estimator.steps[1][1]
        results[phase] = {"month": month, "samples": len(test), "no_shows": sum(actual),
                          "logistic_brier": round(brier_score_loss(actual, predicted), 4),
                          "baseline_brier": round(brier_score_loss(actual, [np.mean([e[2] for e in train])] * len(test)), 4),
                          "average_precision": float(average_precision_score(actual, predicted)),
                          "precision_at_half": float(precision_score(actual, classes, zero_division=0)),
                          "recall_at_half": float(recall_score(actual, classes, zero_division=0)),
                          "f1_at_half": float(f1_score(actual, classes, zero_division=0)),
                          "confusion_matrix": confusion_matrix(actual, classes, labels=[0, 1]).tolist(),
                          "roc": [{"x": float(x), "y": float(y), "threshold": float(t) if np.isfinite(t) else None}
                                  for x, y, t in zip(fpr, tpr, thresholds)],
                          "precision_recall": [{"x": float(x), "y": float(y)} for x, y in zip(recall, precision)],
                          "calibration": calibration,
                          "model": {"intercept": float(classifier.intercept_[0]), "coefficients": classifier.coef_[0].tolist(),
                                    "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(), "training_samples": len(train),
                                    "features": ["lead_days", "previous_completed", "previous_no_show", "previous_cancelled", "days_since_completed_or_180",
                                                 "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]},
                          "roc_auc": round(roc_auc_score(actual, predicted), 4) if len(set(actual)) > 1 else None}
    return {"status": "evaluated", "prediction_time": "booking time", "metrics": results,
            "selected_method": "logistic_regression" if results["validation"]["logistic_brier"] < results["validation"]["baseline_brier"] else "historical_rate"}


def run(directory):
    rows, calendar = load(directory)
    months = sorted({r["scheduled_start"].strftime("%Y-%m") for r in rows})
    summary = {m: {"patients": len({r["patient_id"] for r in rows if r["scheduled_start"].strftime("%Y-%m") == m}),
                   "outcomes": dict(Counter(r["status"] for r in rows if r["scheduled_start"].strftime("%Y-%m") == m))} for m in months}
    end_visit = max(r["scheduled_start"].date() for r in rows)
    observed_end = end_visit.replace(day=month_calendar.monthrange(end_visit.year, end_visit.month)[1]) + timedelta(days=1)
    retention_labels = []
    patients = {r["patient_id"] for r in rows}
    for month in months[1:]:
        cutoff = date.fromisoformat(month + "-01")
        eligible = {p for p in patients if any(r["patient_id"] == p and r["status"] == "completed"
                    and r["status_recorded_at"].date() < cutoff for r in rows)}
        mature = cutoff + timedelta(days=90) <= observed_end
        returned = sum(any(r["patient_id"] == p and r["status"] == "completed"
                       and cutoff <= r["scheduled_start"].date() < cutoff + timedelta(days=90) for r in rows) for p in eligible) if mature else None
        retention_labels.append({"cutoff": cutoff.isoformat(), "eligible": len(eligible), "fully_observed": mature,
                                 "returned_90_days": returned})
    last_training_cutoff = observed_end - timedelta(days=180)
    training_patients = {r["patient_id"] for r in rows if r["status"] == "completed"
                         and r["status_recorded_at"].date() < last_training_cutoff}
    return {"source": "User-supplied generated appointment history", "schema_version": 1,
            "dataset_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in ("appointments.csv", "clinic_calendar.csv")},
            "validation": {"status": "passed", "appointments": len(rows), "patients": len({r["patient_id"] for r in rows}), "months": summary},
            "busyness": count_backtest(rows, calendar, "completed"), "no_show_counts": count_backtest(rows, calendar, "no_show"),
            "individual_no_shows": no_show_backtest(rows),
            "retention": {"status": "insufficient_observation", "target_days": 90,
                          "label_diagnostics": retention_labels,
                          "latest_training_cutoff_for_independent_holdout": last_training_cutoff.isoformat(),
                          "training_patients_available": len(training_patients),
                          "message": f"An independent 90-day holdout leaves only {len(training_patients)} patients with prior completed visits for training at {last_training_cutoff}. Additional history or follow-up is needed for a meaningful retention backtest."}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.directory)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in ("busyness", "no_show_counts")}, indent=2))
