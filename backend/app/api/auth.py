from fastapi import APIRouter, Request, Response
from sqlmodel import select

from ..db.models import User as UserRow
from ..services.auth import CSRF_COOKIE, SESSION_COOKIE, hash_password, new_csrf_token, verify_password
from .deps import DB, ApiError, Svc, User, audit
from .schemas import LoginIn, PasswordIn, SessionOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session(resp: Response, svc, user: str) -> str:
    csrf = new_csrf_token()
    ttl = svc.settings.server.session_hours * 3600
    resp.set_cookie(SESSION_COOKIE, svc.signer.dumps({"sub": user, "csrf": csrf}, ttl), max_age=ttl,
                    httponly=True, samesite="lax", path="/")  # fmt: skip
    resp.set_cookie(CSRF_COOKIE, csrf, max_age=ttl, httponly=False, samesite="lax", path="/")
    return csrf


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, request: Request, response: Response, svc: Svc, s: DB) -> SessionOut:
    ip = request.client.host if request.client else "?"
    if not svc.login_limiter.allow(ip):
        raise ApiError(429, "rate_limited", "Too many sign-in attempts. Wait a minute and try again.")
    user = s.exec(select(UserRow).where(UserRow.username == body.username)).first()
    if user is None or not verify_password(user.password_hash, body.password):
        raise ApiError(401, "bad_credentials", "Wrong username or password.")
    csrf = _set_session(response, svc, user.username)
    audit(s, user.username, "login")
    s.commit()
    return SessionOut(user=user.username, csrf_token=csrf)


@router.post("/logout", status_code=204)
def logout(response: Response, user: User) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.get("/me", response_model=SessionOut)
def me(request: Request, user: User) -> SessionOut:
    return SessionOut(user=user, csrf_token=request.cookies.get(CSRF_COOKIE, ""))


@router.post("/password", status_code=204)
def change_password(body: PasswordIn, user: User, s: DB) -> None:
    row = s.exec(select(UserRow).where(UserRow.username == user)).one()
    if not verify_password(row.password_hash, body.current):
        raise ApiError(400, "bad_credentials", "The current password is wrong.")
    row.password_hash = hash_password(body.new)
    s.add(row)
    audit(s, user, "change_password")
    s.commit()
