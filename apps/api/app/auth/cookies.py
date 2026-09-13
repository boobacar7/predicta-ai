from starlette.responses import Response

from app.core.config import Settings

_COOKIE_PATH = "/"


def apply_session_cookies(response: Response, settings: Settings, *, session_token: str, csrf_token: str) -> None:
    secure = settings.session_cookie_secure
    max_age = settings.session_ttl_seconds
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=max_age,
        path=_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        path=_COOKIE_PATH,
        secure=secure,
        httponly=False,
        samesite="lax",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    secure = settings.session_cookie_secure
    for name, httponly in (
        (settings.session_cookie_name, True),
        (settings.csrf_cookie_name, False),
    ):
        response.delete_cookie(
            key=name,
            path=_COOKIE_PATH,
            secure=secure,
            httponly=httponly,
            samesite="lax",
        )
