"""Request dependencies: services, DB session, authenticated user, CSRF and a common error shape."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from ..db.session import engine
from ..services.auth import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from ..services.state import AppServices

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(status, {"code": code, "message": message, "details": details})


def services(request: Request) -> AppServices:
    return request.app.state.vs


def db() -> Iterator[Session]:
    with Session(engine(), expire_on_commit=False) as s:
        yield s


def current_user(request: Request, svc: Annotated[AppServices, Depends(services)]) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    data = svc.signer.loads(token) if token else None
    if not data:
        raise ApiError(401, "unauthenticated", "Sign in to continue.")
    if request.method not in SAFE_METHODS:
        sent, cookie = request.headers.get(CSRF_HEADER), request.cookies.get(CSRF_COOKIE)
        if not sent or not cookie or sent != cookie or sent != data.get("csrf"):
            raise ApiError(403, "csrf", "Security token missing or expired. Reload the page.")
    return str(data["sub"])


Svc = Annotated[AppServices, Depends(services)]
DB = Annotated[Session, Depends(db)]
User = Annotated[str, Depends(current_user)]


def require_cameras(svc: AppServices):
    if svc.cameras is None:
        raise ApiError(
            503, "model_unavailable", f"The detection model is not loaded: {svc.model_error or 'starting'}"
        )
    return svc.cameras


def audit(s: Session, user: str, action: str, target: str | None = None, details: dict | None = None) -> None:
    from ..db.models import AuditLog

    s.add(AuditLog(user=user, action=action, target=target, details=details))
