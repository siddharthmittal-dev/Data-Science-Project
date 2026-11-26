"""Train synthetic 90-day return probabilities without modifying application data."""
import json
import random
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, average_precision_score, precision_score, recall_score

from app.config import get_settings
from app.services.retention import ARTIFACT, FEATURES, patient_features, probability


def generate(end, population=500):
    rng = random.Random(57)
    start = end - timedelta(days=719)
    patients = []
    for _ in range(population):
        events = []
        index = rng.randint(0, 100)
        interval = rng.choice([30, 45, 60, 90, 120, 180])
        stop = rng.randint(300, 650) if rng.random() < 0.35 else 720
        while index < stop:
            events.append({"day": start + timedelta(days=index),
                           "status": rng.choices(["completed", "cancelled", "no_show"], [85, 10, 5])[0]})
            index += max(14, round(rng.gauss(interval, interval * 0.3)))
        patients.append(events)
    return start, patients


def snapshots(patients, dates, end):
    x, y = [], []
    for cutoff in dates:
        if cutoff + timedelta(days=90) > end:
            raise ValueError("Return labels need a full 90-day observation window")
        for events in patients:
            values = patient_features(events, cutoff)
            if values is not None:
                x.append(values)
                y.append(int(any(e["status"] == "completed" and cutoff <= e["day"] < cutoff + timedelta(days=90) for e in events)))
    return x, y


def evaluate(y, probabilities):
    predicted = np.array(probabilities) >= 0.5
    bins = []
    for lo in (0, 0.2, 0.4, 0.6, 0.8):
        selected = [i for i, p in enumerate(probabilities) if lo <= p < lo + 0.2 or (lo == 0.8 and p == 1)]
        if selected:
            bins.append({"range": [lo, round(lo + 0.2, 1)], "count": len(selected),
                         "predicted": round(float(np.mean([probabilities[i] for i in selected])), 3),
                         "observed": round(float(np.mean([y[i] for i in selected])), 3)})
    return {"samples": len(y), "return_rate": round(float(np.mean(y)), 3),
            "brier": round(float(brier_score_loss(y, probabilities)), 3),
            "roc_auc": round(float(roc_auc_score(y, probabilities)), 3),
            "average_precision": round(float(average_precision_score(y, probabilities)), 3),
            "precision_at_half": round(float(precision_score(y, predicted, zero_division=0)), 3),
            "recall_at_half": round(float(recall_score(y, predicted, zero_division=0)), 3), "calibration": bins}


def train(end):
    start, patients = generate(end)
    validation_day = end - timedelta(days=180)
    holdout_day = end - timedelta(days=90)
    training_dates = [start + timedelta(days=i) for i in range(180, 450, 30)]
    x, y = snapshots(patients, training_dates, end)
    if max(training_dates) + timedelta(days=90) > validation_day:
        raise ValueError("Training outcomes overlap validation origin")
    estimator = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(x, y)
    scaler, classifier = estimator.steps[0][1], estimator.steps[1][1]
    metrics = {}
    rate = float(np.mean(y))
    calibration_x, calibration_y = snapshots(patients, [validation_day], end)
    calibrator = LogisticRegression(max_iter=2000).fit(estimator.decision_function(calibration_x).reshape(-1, 1), calibration_y)
    for name, cutoff in (("validation", validation_day), ("holdout", holdout_day)):
        vx, vy = snapshots(patients, [cutoff], end)
        probabilities = estimator.predict_proba(vx)[:, 1] if name == "validation" else calibrator.predict_proba(estimator.decision_function(vx).reshape(-1, 1))[:, 1]
        baseline_rate = rate if name == "validation" else float(np.mean(calibration_y))
        metrics[name] = {"logistic": evaluate(vy, probabilities),
                         "baseline": evaluate(vy, np.full(len(vy), baseline_rate))}
    selected = "logistic" if metrics["validation"]["logistic"]["brier"] < metrics["validation"]["baseline"]["brier"] else "baseline"
    artifact = {"schema_version": 1, "features": FEATURES, "seed": 57, "source": "synthetic", "population": 500,
                "observation_end": end.isoformat(), "trained_at": datetime.now(UTC).isoformat(),
                "training_label_end": (max(training_dates) + timedelta(days=90)).isoformat(),
                "validation_origin": validation_day.isoformat(), "holdout_origin": holdout_day.isoformat(),
                "training_samples": len(y), "baseline_probability": float(np.mean(calibration_y)), "selected_method": selected,
                "metrics": metrics, "model": {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                "coefficients": classifier.coef_[0].tolist(), "intercept": float(classifier.intercept_[0]),
                "calibration_slope": float(calibrator.coef_[0][0]), "calibration_intercept": float(calibrator.intercept_[0])}}
    artifact["examples"] = [{"name": f"Example patient {i + 1:03}", "features": values,
                             "probability": probability(values, artifact) if selected == "logistic" else round(rate, 3)}
                            for i, events in enumerate(patients[:8]) if (values := patient_features(events, end)) is not None]
    return artifact


if __name__ == "__main__":
    artifact = train(datetime.now(ZoneInfo(get_settings().clinic_timezone)).date())
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected": artifact["selected_method"], "holdout": artifact["metrics"]["holdout"]}, indent=2))
