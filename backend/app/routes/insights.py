from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_staff, require_admin
from pathlib import Path
from app.models import User
from app.services.insights import build_insights
from app.services.demand import ARTIFACT
from app.check_demand import run
from datetime import date
import json
from fastapi import HTTPException

router = APIRouter()


@router.get("/insights/csv-evaluation")
def csv_evaluation(_: User = Depends(require_admin)):
    path = Path(__file__).resolve().parents[2] / "data" / "clinic-csv-evaluation.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(503, detail={"code": "evaluation_unavailable", "message": "CSV evaluation is unavailable. Run the CSV validation and backtest command."}) from None


@router.get("/insights")
def insights(user: User = Depends(require_staff), db: Session = Depends(get_db)) -> dict:
    return build_insights(db)


@router.get("/insights/replay")
def replay(origin: date, _: User = Depends(require_staff)):
    try:
        rows = json.loads(ARTIFACT.read_text(encoding="utf-8"))["history"]
        return run(rows, origin)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(422, detail={"code": "invalid_replay", "message": "Choose a date with 65 earlier and seven later days in the saved evaluation dataset."}) from exc
