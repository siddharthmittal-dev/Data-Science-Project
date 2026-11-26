import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment, Slot
from app.config import get_settings
from app.services.insights import FORECAST_LABEL, FORECAST_METHOD, build_insights, forecast

START = date(2026, 1, 5)  # Monday
MONDAYS_BEFORE_START = [date(2025, 12, 8), date(2025, 12, 15), date(2025, 12, 22), date(2025, 12, 29)]
FOUR_MONDAY_VALUES = [10, 20, 30, 40]  # mean 25.0


def test_start_is_monday() -> None:
    assert START.weekday() == 0


# Unit tests for forecast()


def test_forecast_is_mean_of_last_four_same_weekdays() -> None:
    history = dict(zip(MONDAYS_BEFORE_START, FOUR_MONDAY_VALUES, strict=True))

    assert forecast(history, START, days=1) == [(START, 25.0)]


def test_forecast_ignores_fifth_and_older_same_weekday() -> None:
    history = dict(zip(MONDAYS_BEFORE_START, FOUR_MONDAY_VALUES, strict=True))
    history[date(2025, 12, 1)] = 1000

    assert forecast(history, START, days=1) == [(START, 25.0)]


def test_forecast_uses_available_weeks_when_fewer_than_four() -> None:
    history = {date(2025, 12, 22): 30, date(2025, 12, 29): 50}

    assert forecast(history, START, days=1) == [(START, 40.0)]


def test_forecast_without_history_is_zero_for_seven_days() -> None:
    assert forecast({}, START) == [(START + timedelta(days=i), 0.0) for i in range(7)]


def test_forecast_rounds_to_one_decimal() -> None:
    history = dict(zip(MONDAYS_BEFORE_START[1:], [10, 10, 11], strict=True))  # mean 10.333...

    assert forecast(history, START, days=1) == [(START, 10.3)]


def test_forecast_never_uses_the_target_day_itself() -> None:
    history = dict(zip(MONDAYS_BEFORE_START, FOUR_MONDAY_VALUES, strict=True))
    history[START] = 999

    assert forecast(history, START, days=1) == [(START, 25.0)]


def test_forecast_does_not_feed_forecasts_back() -> None:
    history = dict(zip(MONDAYS_BEFORE_START, FOUR_MONDAY_VALUES, strict=True))

    points = forecast(history, START, days=8)

    # Jan 12 must use only real Mondays (Dec 8 to Dec 29), not the forecast for Jan 5.
    assert points[7] == (START + timedelta(days=7), 25.0)


def test_forecast_is_deterministic() -> None:
    history = dict(zip(MONDAYS_BEFORE_START, FOUR_MONDAY_VALUES, strict=True))

    assert forecast(history, START) == forecast(history, START)


# build_insights() against the seeded database


def test_build_insights_history_ends_yesterday_of_given_today(db: Session) -> None:
    last_day = date(2026, 11, 20)

    body = build_insights(db, today=last_day + timedelta(days=1))

    assert len(body["history"]) == 30
    assert body["history"][-1]["day"] == last_day.isoformat()


# Endpoint tests


def test_insights_without_login_is_401(client: TestClient) -> None:
    response = client.get("/api/insights")

    assert response.status_code == 401


def test_insights_patient_is_403(login) -> None:
    response = login("patient").get("/api/insights")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"


@pytest.mark.parametrize("role", ["receptionist", "admin"])
def test_insights_staff_gets_200(login, role: str) -> None:
    response = login(role).get("/api/insights")

    assert response.status_code == 200


def test_insights_response_shape(login) -> None:
    body = login("admin").get("/api/insights").json()
    today = datetime.now(ZoneInfo(get_settings().clinic_timezone)).date()

    assert body["window_days"] == 30
    assert body["forecast"]["label"] == FORECAST_LABEL
    assert body["forecast"]["method"] == FORECAST_METHOD
    assert body["forecast"]["status"] == "limited_history"

    history = body["history"]
    assert len(history) == 30
    assert [row["day"] for row in history] == sorted(row["day"] for row in history)
    assert history[0]["day"] == (today - timedelta(days=30)).isoformat()
    assert history[-1]["day"] == (today - timedelta(days=1)).isoformat()
    assert set(history[0]) == {"day", "booked", "completed", "cancelled", "no_show", "capacity", "data_status"}

    points = body["forecast"]["points"]
    assert len(points) == 7
    assert points[0]["day"] == (today + timedelta(days=1)).isoformat()
    assert {"day", "predicted_booked", "confirmed", "capacity", "remaining_capacity", "utilisation"} <= set(points[0])


def test_insights_history_matches_database(login, db: Session) -> None:
    body = login("admin").get("/api/insights").json()
    timezone = ZoneInfo(get_settings().clinic_timezone)
    expected = {}
    for appointment, slot in db.execute(select(Appointment, Slot).join(Slot, Appointment.slot_id == Slot.id)):
        day = slot.starts_at.astimezone(timezone).date().isoformat()
        values = expected.setdefault(day, {"booked": 0, "cancelled": 0})
        values["booked"] += 1
        values["cancelled"] += appointment.status == "cancelled"
    for row in body["history"]:
        assert row["booked"] == expected.get(row["day"], {}).get("booked", 0)
        assert row["cancelled"] == expected.get(row["day"], {}).get("cancelled", 0)


def test_insights_totals_and_rates(login) -> None:
    body = login("admin").get("/api/insights").json()
    rows = body["history"]
    totals = body["totals"]

    for key in ("booked", "completed", "cancelled", "no_show"):
        assert totals[key] == sum(row[key] for row in rows)
    assert totals["booked"] > 0
    assert totals["cancellation_rate"] == round(totals["cancelled"] / totals["booked"], 3)
    assert totals["no_show_rate"] == round(totals["no_show"] / totals["booked"], 3)


def test_insights_forecast_respects_confirmed_capacity_and_unknown_schedule(login) -> None:
    body = login("admin").get("/api/insights").json()
    for point in body["forecast"]["points"]:
        if point["capacity"] and point["predicted_booked"] is not None:
            assert point["confirmed"] <= point["predicted_booked"] <= point["capacity"]
            assert point["remaining_capacity"] == round(point["capacity"] - point["predicted_booked"], 1)
        elif not point["capacity"]:
            assert point["predicted_booked"] is None
            assert point["schedule_status"] == "no_schedule"
    if body["business"]["expected_visits"] is not None:
        assert body["business"]["expected_visits"] >= body["business"]["confirmed_visits"]


def test_insights_strings_never_mention_chronos(login) -> None:
    body = login("admin").get("/api/insights").json()

    assert "chronos" not in json.dumps(body).lower()


def test_legacy_slots_are_preserved_but_not_counted_as_capacity(db):
    from app.clinic import slots_for_day
    day = date(2026, 11, 23)
    valid = slots_for_day(day, 1)[0]
    # Use dates outside the seeded schedule to avoid existing slot collisions.
    valid.starts_at = valid.starts_at.replace(year=2027)
    valid.ends_at = valid.ends_at.replace(year=2027)
    valid_day = valid.starts_at.date()
    # Preserve a separate after-hours legacy slot on the same clinic day.
    legacy = Slot(doctor_id=1, starts_at=valid.starts_at.replace(hour=22), ends_at=valid.ends_at.replace(hour=22))
    db.add_all([valid, legacy])
    db.commit()
    before = len(db.scalars(select(Slot)).all())
    body = build_insights(db, today=valid_day - timedelta(days=1))
    point = next(p for p in body["forecast"]["points"] if p["day"] == valid_day.isoformat())
    assert point["capacity"] == 1
    assert len(db.scalars(select(Slot)).all()) == before
