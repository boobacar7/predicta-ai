from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.auth.service import is_public_request, load_identity, require_csrf
from app.core.clock import Clock
from app.core.errors import ApiError, UnauthorizedError, problem_response
from app.db.session import session_scope


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        settings = request.app.state.settings
        request.state.identity = None
        if settings.auth_bypass:
            return await call_next(request)
        if is_public_request(request.url.path, request.method):
            return await call_next(request)
        clock: Clock = request.app.state.container.clock
        try:
            with session_scope(settings) as session:
                identity = load_identity(session, settings, request, now=clock.now())
                if identity is None:
                    raise UnauthorizedError()
                require_csrf(settings, request, identity)
                request.state.user_id = identity.user.id
                request.state.user_email = identity.user.email
                request.state.session_id = identity.session.id
        except ApiError as exc:
            return problem_response(
                request=request,
                status_code=exc.status_code,
                title=exc.title,
                detail=exc.detail,
                type_uri=exc.type_uri,
                instance=exc.instance,
            )
        return await call_next(request)
