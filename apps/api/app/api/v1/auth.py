from fastapi import APIRouter, Request, Response
from pydantic import Field

from app.api.deps import envelope
from app.auth.cookies import apply_session_cookies, clear_session_cookies
from app.auth.service import load_identity, login, public_user, require_csrf, revoke_session
from app.core.errors import UnauthorizedError
from app.db.session import session_scope
from app.schemas import ApiModel

router = APIRouter(tags=["Auth"])


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/login")
def login_route(request: Request, body: LoginRequest, response: Response) -> dict[str, object]:
    settings = request.app.state.settings
    now = request.app.state.container.clock.now()
    with session_scope(settings) as session:
        user, session_token, csrf_token = login(
            session,
            settings,
            email=body.email,
            password=body.password,
            now=now,
        )
        payload = {"user": public_user(user), "csrf_token": csrf_token}
    apply_session_cookies(response, settings, session_token=session_token, csrf_token=csrf_token)
    return envelope(request, payload)


@router.post("/auth/logout")
def logout_route(request: Request, response: Response) -> dict[str, object]:
    settings = request.app.state.settings
    now = request.app.state.container.clock.now()
    if not settings.auth_bypass:
        with session_scope(settings) as session:
            identity = load_identity(session, settings, request, now=now)
            if identity is None:
                raise UnauthorizedError()
            require_csrf(settings, request, identity)
            revoke_session(session, identity, now=now)
    clear_session_cookies(response, settings)
    return envelope(request, {"logged_out": True})


@router.get("/auth/session")
def session_route(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    if settings.auth_bypass:
        return envelope(request, {"user": None, "bypass": True})
    now = request.app.state.container.clock.now()
    with session_scope(settings) as session:
        identity = load_identity(session, settings, request, now=now)
        if identity is None:
            raise UnauthorizedError()
        payload = {"user": public_user(identity.user), "bypass": False}
    return envelope(request, payload)
