from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserSession

SESSION_COOKIE = "session"
STAFF_ROLES = ("receptionist", "admin")


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(401, detail={"code": "unauthenticated", "message": "Sign in to continue."})
    user = db.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(UserSession.token == session_token, UserSession.expires_at > datetime.now(UTC))
    )
    if user is None:
        raise HTTPException(401, detail={"code": "unauthenticated", "message": "Your session has ended. Sign in again."})
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in STAFF_ROLES:
        raise HTTPException(403, detail={"code": "forbidden", "message": "This action is for clinic staff."})
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, detail={"code": "admin_only", "message": "Patient medical history requires admin access."})
    return user
