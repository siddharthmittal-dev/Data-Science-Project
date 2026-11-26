import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import SESSION_COOKIE, get_current_user
from app.models import User, UserSession
from app.services.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_HOURS = 8


DUMMY_HASH = hash_password("invalid-account-timing-placeholder")


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("Enter a valid email address")
        local, domain = value.split("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Enter a valid email address")
        return value


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=200)
    role: Literal["patient", "receptionist", "admin"]

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is required")
        return value.strip()


def _user_out(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def _session(user: User, response: Response, db: Session, old_token: str | None) -> dict:
    if old_token:
        db.execute(delete(UserSession).where(UserSession.token == old_token))
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token=token, user_id=user.id, created_at=now, expires_at=now + timedelta(hours=SESSION_HOURS)))
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
        path="/",
    )
    return _user_out(user)


@router.get("/available-roles")
def available_roles(db: Session = Depends(get_db)) -> dict:
    if not get_settings().signup_enabled:
        return {"roles": []}
    claimed = set(db.scalars(select(User.role).where(User.password_hash.is_not(None))))
    return {"roles": [role for role in ("patient", "receptionist", "admin") if role not in claimed]}


@router.post("/signup", status_code=201)
def signup(body: Registration, response: Response,
           session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
           db: Session = Depends(get_db)) -> dict:
    if not get_settings().signup_enabled:
        raise HTTPException(403, detail={"code": "registration_closed",
                            "message": "Account registration is closed. Sign in with your existing account."})
    user = User(name=body.name, email=body.email, role=body.role,
                password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
        return _session(user, response, db, session_token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "account_unavailable",
                            "message": "This role or email is already registered. Sign in with the existing account."}) from None


@router.post("/login")
def login(body: Credentials, response: Response,
          session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
          db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(func.lower(User.email) == body.email))
    valid = verify_password(body.password, user.password_hash if user and user.password_hash else DUMMY_HASH)
    if not user or not user.password_hash or not valid:
        raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Email or password is incorrect."})
    return _session(user, response, db, session_token)


@router.post("/logout", status_code=204)
def logout(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> Response:
    if session_token:
        db.execute(delete(UserSession).where(UserSession.token == session_token))
        db.commit()
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=get_settings().cookie_secure)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return _user_out(user)
