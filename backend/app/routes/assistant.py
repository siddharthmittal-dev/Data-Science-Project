from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.routes.appointments import AppointmentItem, load_item
from app.services import assistant
from app.services.errors import ServiceError
from app.routes.patient_documents import Turn
from app.services.workspace import knowledge_reply

router = APIRouter(prefix="/assistant", tags=["assistant"])

Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class MessageIn(BaseModel):
    message: Message
    patient_id: int | None = None
    workspace: bool = False
    context: Literal["auto", "documents", "insights"] = "auto"
    document_id: str | None = Field(default=None, max_length=100)
    history: list[Turn] = Field(default_factory=list, max_length=6)


class CitationOut(BaseModel):
    slug: str
    title: str
    scope: Literal["guide", "patient", "insights"] = "guide"
    patient_id: int | None = None


class ProposedActionOut(BaseModel):
    id: int
    type: str
    summary: str
    params: dict


class MessageOut(BaseModel):
    reply: str
    citations: list[CitationOut]
    proposed_action: ProposedActionOut | None
    ai_notice: str | None = None
    origin: str | None = None


class ConfirmOut(BaseModel):
    status: Literal["confirmed"]
    appointment: AppointmentItem


class DismissOut(BaseModel):
    status: Literal["dismissed"]


def _http(err: ServiceError) -> HTTPException:
    return HTTPException(err.http_status, detail={"code": err.code, "message": err.message})


@router.post("/message", response_model=MessageOut, response_model_exclude_unset=True)
def send_message(
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    if body.workspace:
        answer = knowledge_reply(db, user, body.message, body.document_id,
                                 [turn.model_dump() for turn in body.history], body.context, body.patient_id)
        if answer is not None:
            return MessageOut(**answer, proposed_action=None)
    try:
        result, action = assistant.handle_message(db, user, body.message, body.patient_id)
    except ServiceError as err:
        raise _http(err) from err
    proposed = None
    if action is not None:
        proposed = {"id": action.id, "type": action.type, "summary": action.summary, "params": action.params}
    return MessageOut(reply=result.reply, citations=result.citations, proposed_action=proposed)


@router.post("/actions/{action_id}/confirm", response_model=ConfirmOut)
def confirm_action(
    action_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConfirmOut:
    try:
        appointment = assistant.confirm(db, user, action_id)
    except ServiceError as err:
        raise _http(err) from err
    return ConfirmOut(status="confirmed", appointment=load_item(db, appointment.id, user))


@router.post("/actions/{action_id}/dismiss", response_model=DismissOut)
def dismiss_action(
    action_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DismissOut:
    try:
        assistant.dismiss(db, user, action_id)
    except ServiceError as err:
        raise _http(err) from err
    return DismissOut(status="dismissed")
