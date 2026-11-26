"""Forecast leakage, serialization parity, fallback and appointment event checks."""

import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from app.models import Appointment, AppointmentEvent, Slot
from app.services import demand
from app.services.appointments import book, cancel, reschedule
from app.services.errors import ServiceError
from app.train_demand import fit, synthetic_history, train
from app.check_demand import run


def test_synthetic_data_is_reproducible_and_reconciles():
    rows = synthetic_history(date(2026, 11, 20))
    assert rows == synthetic_history(date(2026, 11, 20))
    assert len(rows) == 365
    for row in rows:
        assert row["booked"] == row["completed"] + row["cancelled"] + row["no_show"]
        assert row["demand"] == row["completed"] + row["no_show"]
        assert 0 <= row["demand"] <= row["capacity"]


def test_historical_replay_freezes_inputs_and_exposes_errors():
    rows = synthetic_history(date(2026, 11, 20))
    before = run(rows, date(2026, 11, 9))
    assert before["known_through"] == "2026-11-08"
    assert len(before["points"]) == 7
    assert all(v >= 0 for v in before["mae_all_days"].values())
    for row in rows:
        if row["day"] >= "2026-11-09":
            row["demand"] = 20
    after = run(rows, date(2026, 11, 9))
    assert [p["regression"] for p in before["points"]] == [p["regression"] for p in after["points"]]
    assert before["mae_all_days"] != after["mae_all_days"]
    with pytest.raises(ValueError):
        run(rows, date(2026, 11, 20))


def test_origin_features_and_predictions_do_not_use_future_actuals():
    rows = synthetic_history(date(2026, 11, 20))
    known = rows[:250]
    model = fit(known)
    target = date.fromisoformat(rows[257]["day"])
    before = demand.predict(known, target, 96, model)
    for row in rows[250:]:
        row["demand"] = 99999
    assert demand.predict(known, target, 96, model) == before


def test_frozen_origin_same_weekday_features_do_not_feed_predictions_back():
    history = [{"day": "2026-11-02", "demand": 20}, {"day": "2026-11-09", "demand": 30}]
    values = demand.features(history, date(2026, 11, 23), date(2026, 1, 1))
    assert values[-2:] == [30, 25]
    assert demand.predict(history, date(2026, 11, 23), 96) == 25


def test_model_serialization_matches_training_predictions():
    rows = synthetic_history(date(2026, 11, 20))
    model = fit(rows)
    loaded = json.loads(json.dumps(model))
    target = date(2026, 11, 23)
    assert demand.predict(rows, target, 96, loaded) == demand.predict(rows, target, 96, model)
    assert demand.predict(rows, target, 0, loaded) == 0
    loaded["intercept"] = -1e9
    assert demand.predict(rows, target, 96, loaded) == 0
    loaded["intercept"] = 1e9
    assert demand.predict(rows, target, 96, loaded) == 96


def test_selection_uses_validation_and_holdout_has_all_horizons():
    artifact = train(date(2026, 11, 20))
    validation = artifact["metrics"]["validation"]
    expected = "linear_regression" if validation["linear_regression"]["mae"] < validation["baseline"]["mae"] else "baseline"
    assert artifact["selected_method"] == expected
    for metrics in artifact["metrics"]["holdout"].values():
        assert metrics["samples"] == 343
        assert len(metrics["mae_by_horizon"]) == 7
        assert metrics["rmse"] >= metrics["mae"]


def test_demo_missing_corrupt_and_stale_fallback(tmp_path, monkeypatch):
    path = tmp_path / "model.json"
    monkeypatch.setattr(demand, "ARTIFACT", path)
    assert demand.demo_forecast(date(2026, 11, 21))["status"] == "unavailable"
    path.write_text("invalid json")
    assert demand.demo_forecast(date(2026, 11, 21))["status"] == "unavailable"
    artifact = train(date(2026, 11, 20))
    path.write_text(json.dumps(artifact))
    assert demand.demo_forecast(date(2026, 11, 29))["status"] == "stale"
    ready = demand.demo_forecast(date(2026, 11, 21))
    assert ready["status"] == "ready"
    assert len(ready["points"]) == 7
    assert ready["training_end"] == "2026-11-20"


def test_events_record_changes_in_same_transaction(db):
    now = datetime.now(UTC)
    slots = db.scalars(select(Slot).where(Slot.starts_at > now).order_by(Slot.id)).all()
    used = set(db.scalars(select(Appointment.slot_id).where(Appointment.status == "booked")))
    free = [slot for slot in slots if slot.id not in used]
    created = book(db, patient_id=1, slot_id=free[0].id, reason="Synthetic test")
    reschedule(db, appointment_id=created.id, new_slot_id=free[1].id)
    cancel(db, appointment_id=created.id)
    events = db.scalars(select(AppointmentEvent).where(AppointmentEvent.appointment_id == created.id)
                        .order_by(AppointmentEvent.id)).all()
    assert [e.kind for e in events] == ["booked", "rescheduled", "cancelled"]
    assert events[1].previous_slot_id == free[0].id
    assert events[1].slot_id == free[1].id
    assert events[2].status == "cancelled"
    count = db.scalar(select(func.count(AppointmentEvent.id)))
    with pytest.raises(ServiceError):
        reschedule(db, appointment_id=created.id, new_slot_id=free[2].id)
    assert db.scalar(select(func.count(AppointmentEvent.id))) == count


def test_live_history_uses_clinic_date_not_utc(db):
    from app.services.insights import build_insights

    # 20:00 UTC on Jan 1 is Jan 2 in the configured clinic timezone.
    slot = Slot(doctor_id=1, starts_at=datetime(2026, 1, 1, 20, tzinfo=UTC),
                ends_at=datetime(2026, 1, 1, 20, 30, tzinfo=UTC))
    db.add(slot)
    db.flush()
    db.add(Appointment(patient_id=1, slot_id=slot.id, status="completed", reason="Timezone test"))
    db.commit()
    body = build_insights(db, today=date(2026, 1, 3))
    assert body["history"][-1]["day"] == "2026-01-02"
    assert body["history"][-1]["completed"] == 1
