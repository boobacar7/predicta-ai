from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth.identities import AuthenticatedIdentity
from app.auth.passwords import dummy_verify, hash_password, verify_password
from app.auth.tokens import hash_token, new_token, tokens_match
from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.models import AuthSession, User

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_PUBLIC_EXACT = frozenset({"/health", "/ready", "/openapi.json", "/docs", "/redoc"})
_PUBLIC_PREFIXES = ("/docs", "/redoc")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_public_request(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return True
    normalized = path.rstrip("/") or "/"
    if normalized in _PUBLIC_EXACT or path in _PUBLIC_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return True
    if normalized == "/api/v1/auth/login" and method == "POST":
        return True
    if normalized == "/api/v1/auth/session" and method == "GET":
        return True
    return False


def normalize_email(email: str) -> str:
    return email.strip().lower()


def provision_user(session: Session, *, email: str, password: str, now: datetime) -> User:
    normalized = normalize_email(email)
    existing = session.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        existing.password_hash = hash_password(password)
        existing.updated_at = now
        existing.disabled_at = None
        session.flush()
        return existing
    user = User(
        id=f"usr_{uuid.uuid4().hex}",
        email=normalized,
        password_hash=hash_password(password),
        created_at=now,
        updated_at=now,
        disabled_at=None,
    )
    session.add(user)
    session.flush()
    return user


def login(
    session: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    now: datetime,
) -> tuple[User, str, str]:
    normalized = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized))
    if user is None or user.disabled_at is not None:
        dummy_verify(password)
        raise UnauthorizedError("Invalid email or password.")
    if not verify_password(user.password_hash, password):
        raise UnauthorizedError("Invalid email or password.")
    if normalized not in settings.invite_allowlist:
        raise UnauthorizedError("Invalid email or password.")
    raw_session = new_token()
    raw_csrf = new_token()
    row = AuthSession(
        id=f"ses_{uuid.uuid4().hex}",
        user_id=user.id,
        token_hash=hash_token(raw_session),
        csrf_token_hash=hash_token(raw_csrf),
        expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
        created_at=now,
        last_seen_at=now,
        revoked_at=None,
    )
    session.add(row)
    session.flush()
    return user, raw_session, raw_csrf


def load_identity(
    session: Session, settings: Settings, request: Request, *, now: datetime
) -> AuthenticatedIdentity | None:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        return None
    token_hash = hash_token(raw)
    row = session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if row is None or row.revoked_at is not None or _aware(row.expires_at) <= now:
        return None
    user = session.get(User, row.user_id)
    if user is None or user.disabled_at is not None:
        return None
    if user.email not in settings.invite_allowlist:
        return None
    row.last_seen_at = now
    return AuthenticatedIdentity(user=user, session=row)


def require_csrf(settings: Settings, request: Request, identity: AuthenticatedIdentity) -> None:
    if request.method not in _UNSAFE_METHODS:
        return
    header = request.headers.get(settings.csrf_header_name)
    cookie = request.cookies.get(settings.csrf_cookie_name)
    if not header or not cookie:
        raise ForbiddenError("CSRF token missing.")
    if not tokens_match(header, cookie):
        raise ForbiddenError("CSRF token mismatch.")
    if not tokens_match(hash_token(header), identity.session.csrf_token_hash):
        raise ForbiddenError("CSRF token mismatch.")


def revoke_session(session: Session, identity: AuthenticatedIdentity, *, now: datetime) -> None:
    identity.session.revoked_at = now


def public_user(user: User) -> dict[str, str]:
    return {"id": user.id, "email": user.email}
