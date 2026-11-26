"""Replay a historical seven-day forecast without changing the saved model or DB.

From backend: python -m app.check_demand --origin 2026-11-09
"""

import argparse
import json
from datetime import date

from app.services.demand import ARTIFACT, predict
from app.train_demand import fit


def run(rows: list[dict], origin: date) -> dict:
    index = next((i for i, row in enumerate(rows) if row["day"] == origin.isoformat()), -1)
    if index < 65 or index + 7 >= len(rows):
        raise ValueError("Choose an origin with at least 65 earlier days and seven later observed days.")
    known = rows[:index]
    model = fit(known)
    points = []
    for row in rows[index + 1:index + 8]:
        day = date.fromisoformat(row["day"])
        points.append({"day": row["day"], "actual": row["demand"], "capacity": row["capacity"],
                       "regression": predict(known, day, row["capacity"], model),
                       "baseline": predict(known, day, row["capacity"])})
    open_days = [p for p in points if p["capacity"]]
    return {
        "source": "Historical replay on synthetic data; existing artifact and database unchanged",
        "forecast_origin": origin.isoformat(), "known_through": known[-1]["day"], "points": points,
        "mae_all_days": {name: round(sum(abs(p[name] - p["actual"]) for p in points) / len(points), 3)
                         for name in ("regression", "baseline")},
        "mae_open_days": {name: round(sum(abs(p[name] - p["actual"]) for p in open_days) / len(open_days), 3)
                          if open_days else None for name in ("regression", "baseline")},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    try:
        rows = json.loads(ARTIFACT.read_text(encoding="utf-8"))["history"]
        print(json.dumps(run(rows, args.origin), indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
