from collections.abc import Sequence
from typing import Any

from fastapi import Request

from app.core.container import AppContainer
from app.schemas import Envelope, MatchDetail, OddsSnapshot, PredictionDetail


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def envelope(request: Request, data: Any) -> dict[str, Any]:
    settings = request.app.state.settings
    payload = Envelope(
        data_mode=settings.resolved_data_mode(),
        generated_at=request.app.state.container.clock.now(),
        request_id=request.state.request_id,
        data=data,
    )
    return payload.model_dump(mode="json")


def paginate[T](items: Sequence[T], *, limit: int, offset: int) -> dict[str, Any]:
    return {"items": list(items[offset : offset + limit]), "total": len(items)}


def filter_market(match: MatchDetail, market: str | None, kind: str) -> OddsSnapshot | PredictionDetail | None:
    payload: OddsSnapshot | PredictionDetail | None = match.odds if kind == "odds" else match.prediction
    if payload is None:
        return None
    if market and payload.market != market:
        return None
    return payload
