from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    detail: str
    instance: str | None = None
    request_id: str


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        title: str,
        detail: str,
        type_uri: str = "about:blank",
        instance: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.instance = instance


class NotFoundError(ApiError):
    def __init__(self, detail: str, *, instance: str | None = None) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=detail,
            type_uri="/problems/not-found",
            instance=instance,
        )


class ValidationProblem(ApiError):
    def __init__(self, detail: str, *, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(
            status_code=status_code,
            title="Validation Error",
            detail=detail,
            type_uri="/problems/validation",
        )


class UnprocessableError(ApiError):
    def __init__(self, detail: str, *, type_uri: str, title: str = "Unprocessable Entity") -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title=title,
            detail=detail,
            type_uri=type_uri,
        )


class ConflictError(ApiError):
    def __init__(self, detail: str, *, type_uri: str, title: str = "Conflict") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            title=title,
            detail=detail,
            type_uri=type_uri,
        )


class ServiceUnavailableError(ApiError):
    def __init__(self, detail: str, *, type_uri: str, title: str = "Service Unavailable") -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title=title,
            detail=detail,
            type_uri=type_uri,
        )


class UnauthorizedError(ApiError):
    def __init__(self, detail: str = "Authentication required.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail=detail,
            type_uri="/problems/unauthorized",
        )


class ForbiddenError(ApiError):
    def __init__(self, detail: str = "Request rejected.") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail=detail,
            type_uri="/problems/forbidden",
        )


def problem_response(
    *,
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    type_uri: str = "about:blank",
    instance: str | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    payload = ProblemDetails(
        type=type_uri,
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        request_id=request_id,
    )
    headers = {request.app.state.settings.request_id_header: request_id}
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        media_type="application/problem+json",
        headers=headers,
    )


def _format_validation_errors(errors: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for error in errors:
        loc = ".".join(str(item) for item in error.get("loc", ()) if item != "body")
        message = str(error.get("msg", "invalid"))
        parts.append(f"{loc}: {message}" if loc else message)
    return "; ".join(parts) or "Request validation failed."


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return problem_response(
        request=request,
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        type_uri=exc.type_uri,
        instance=exc.instance,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error."
    return problem_response(
        request=request,
        status_code=exc.status_code,
        title="HTTP Error" if exc.status_code < 500 else "Internal Server Error",
        detail=detail,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    status_code = (
        status.HTTP_422_UNPROCESSABLE_ENTITY
        if request.method in {"POST", "PUT", "PATCH"}
        else status.HTTP_400_BAD_REQUEST
    )
    return problem_response(
        request=request,
        status_code=status_code,
        title="Validation Error",
        detail=_format_validation_errors(list(exc.errors())),
        type_uri="/problems/validation",
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request.app.state.logger.exception("unhandled_error", extra={"error": str(exc)})
    return problem_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected error occurred.",
        type_uri="/problems/internal",
    )
