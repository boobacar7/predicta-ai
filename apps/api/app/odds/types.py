from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal

DataMode = Literal["mock", "live"]
FOOTBALL_1X2_MARKET = "1X2"


class Football1x2Selection(StrEnum):
    HOME = "HOME"
    DRAW = "DRAW"
    AWAY = "AWAY"


def decimal_odds(value: Decimal | float | str) -> Decimal:
    try:
        odds = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Decimal odds must be a finite number greater than 1.") from exc
    if not odds.is_finite() or odds <= 1:
        raise ValueError("Decimal odds must be a finite number greater than 1.")
    return odds


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")


@dataclass(frozen=True, slots=True)
class OddsSelection:
    selection: Football1x2Selection
    decimal_odds: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "decimal_odds", decimal_odds(self.decimal_odds))


@dataclass(frozen=True, slots=True)
class OddsSnapshot:
    id: str
    provider_id: str
    match_id: str
    bookmaker: str
    market: str
    selections: tuple[OddsSelection, ...]
    collected_at: datetime
    available_at: datetime
    source: str
    data_mode: DataMode
    raw_payload_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("id", "provider_id", "match_id", "bookmaker", "market", "source"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must not be empty.")
        _require_aware(self.collected_at, "collected_at")
        _require_aware(self.available_at, "available_at")
        if self.available_at < self.collected_at:
            raise ValueError("available_at must be greater than or equal to collected_at.")
        if self.market != FOOTBALL_1X2_MARKET:
            raise ValueError(f"Unsupported odds market: {self.market}.")
        selections = [item.selection for item in self.selections]
        if not selections:
            raise ValueError("Odds snapshot must contain at least one selection.")
        if len(selections) != len(set(selections)):
            raise ValueError("Odds snapshot contains duplicate selections.")


def is_complete_football_1x2(snapshot: OddsSnapshot) -> bool:
    if snapshot.market != FOOTBALL_1X2_MARKET:
        return False
    return {item.selection for item in snapshot.selections} == set(Football1x2Selection)
