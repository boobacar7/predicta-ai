from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import envelope
from app.db.session import ping_database

router = APIRouter(tags=["Health"])


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return envelope(
        request,
        {
            "status": "ok",
            "env": settings.env,
            "data_mode": settings.resolved_data_mode(),
            "repository": settings.repository,
        },
    )


@router.get("/ready", response_model=None)
def ready(request: Request) -> dict[str, object] | JSONResponse:
    settings = request.app.state.settings
    database_ok = True
    redis_configured = bool(settings.redis_url)
    if settings.repository == "sql":
        database_ok = ping_database(settings)
    payload = {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
        "redis_configured": redis_configured,
        "data_mode": settings.resolved_data_mode(),
    }
    body = envelope(request, payload)
    if database_ok:
        return body
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)
