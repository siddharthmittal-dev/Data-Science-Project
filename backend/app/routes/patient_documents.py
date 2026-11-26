import base64
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.services import patient_documents as service
from app.services.document_loader import MAX_BYTES
from starlette.concurrency import run_in_threadpool
from app.routes.appointments import item_query, to_item
from app.models import Appointment, Slot
from datetime import UTC, datetime

router = APIRouter(prefix="/patient-documents", tags=["patient-documents"])
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: Text


class Question(BaseModel):
    question: Text
    document_id: str | None = Field(default=None, max_length=100)
    history: list[Turn] = Field(default_factory=list, max_length=6)
    patient_id: int | None = None


@router.get("")
def library(patient_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subject = service.document_subject(db, user, patient_id)
    index = service.permitted_index(user, subject)
    return [{"slug": key, "title": doc.title, "pages": len(doc.pages), "kind": doc.kind, "status": doc.status,
             "patient_case_id": doc.patient_case_id}
            for key, doc in index.artifact.documents.items()] if index else []


@router.get("/summary")
def summary(patient_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subject = service.document_subject(db, user, patient_id)
    query = item_query().where(Appointment.patient_id == subject.id)
    if user.role == "receptionist":
        query = query.where(Appointment.status == "booked", Slot.starts_at > datetime.now(UTC))
    appointments = [to_item(row, user).model_dump(mode="json") for row in db.execute(query.order_by(Slot.starts_at))]
    return {"patient": {"id": subject.id, "name": subject.name,
                        "email": subject.email if user.role != "receptionist" else None},
            "appointments": appointments, "access": "current_shared" if user.role == "receptionist" else "full"}


@router.post("/chat")
def chat(body: Question, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.explain(db, user, body.question, body.document_id, [turn.model_dump() for turn in body.history], body.patient_id)


@router.post("/upload", status_code=201)
async def upload(request: Request, filename: Annotated[str, Query(min_length=1, max_length=120)],
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "patient":
        raise HTTPException(403, detail={"code": "patient_only", "message": "Only patients can upload their own records."})
    if request.headers.get("content-type") != "application/octet-stream":
        raise HTTPException(415, detail={"code": "unsupported_media_type", "message": "Send the document as a binary file."})
    if filename != filename.strip() or filename.startswith(".") or any(
        ch in "/\\:" or ord(ch) < 32 or ord(ch) == 127 for ch in filename
    ):
        raise HTTPException(422, detail={"code": "invalid_filename", "message": "Choose a plain filename with a supported extension."})
    user_id = user.id
    # Authentication shares this session and has already opened a read transaction.
    await run_in_threadpool(db.rollback)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, detail={"code": "file_too_large", "message": "Document exceeds 12 MiB."})
        data.extend(chunk)
    return await run_in_threadpool(service.upload_document, db, user_id, filename, bytes(data))


@router.get("/{slug}/pdf")
def pdf(slug: str, patient_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    index = service.permitted_index(user, service.document_subject(db, user, patient_id))
    service.source(index, slug)
    doc = index.artifact.documents.get(slug) if index else None
    if doc is None or not doc.pdf_base64:
        raise HTTPException(404, detail={"code": "pdf_unavailable", "message": "Original PDF unavailable."})
    return Response(base64.b64decode(doc.pdf_base64), media_type="application/pdf",
                    headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="patient-document.pdf"',
                             "X-Content-Type-Options": "nosniff"})


@router.get("/{slug}")
def read(slug: str, patient_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.source(service.permitted_index(user, service.document_subject(db, user, patient_id)), slug)
