import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        settings = request.app.state.settings
        header_name = settings.request_id_header
        incoming = request.headers.get(header_name)
        if incoming and 1 <= len(incoming) <= 128:
            request_id = incoming
        else:
            request_id = f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[header_name] = request_id
        return response
