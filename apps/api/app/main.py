from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.auth.middleware import AuthMiddleware
from app.core.clock import Clock, parse_rfc3339
from app.core.config import Settings, get_settings
from app.core.container import AppContainer
from app.core.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    logger = configure_logging(resolved.log_level)
    clock = Clock(parse_rfc3339(resolved.mock_now)) if resolved.repository == "mock" else Clock()
    docs_enabled = not resolved.is_deployed
    app = FastAPI(
        title="PREDICTA AI API",
        version="1.0.0",
        summary="Sports intelligence API. Predictions are probabilities, never guarantees.",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = resolved
    app.state.logger = logger
    app.state.container = AppContainer(resolved, clock)
    app.state.openapi_contract_path = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"

    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", resolved.request_id_header, resolved.csrf_header_name],
        expose_headers=[resolved.request_id_header],
    )

    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health_router)
    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()
