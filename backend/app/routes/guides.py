from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import ClinicGuide, User
from app.services.document_index import get_index

router = APIRouter(prefix="/guides", tags=["guides"])


class GuideSummary(BaseModel):
    slug: str
    title: str


class GuideOut(GuideSummary):
    body: str


@router.get("", response_model=list[GuideSummary])
def list_guides(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    guides = db.scalars(select(ClinicGuide).order_by(ClinicGuide.id)).all()
    library = [{"slug": g.slug, "title": g.title} for g in guides]
    if index := get_index():
        library.extend({"slug": slug, "title": doc.title} for slug, doc in index.artifact.documents.items())
    return library


@router.get("/{slug}", response_model=GuideOut)
def get_guide(slug: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if slug.startswith("doc-"):
        index = get_index()
        if index and (source := index.source(slug)):
            return source
    guide = db.scalar(select(ClinicGuide).where(ClinicGuide.slug == slug))
    if guide is None:
        raise HTTPException(404, detail={"code": "guide_not_found", "message": "That guide does not exist."})
    return {"slug": guide.slug, "title": guide.title, "body": guide.body}
