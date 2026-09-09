from dataclasses import dataclass
from datetime import date

from app.schemas import MatchStatus, SportCode


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    sport: SportCode | None = None
    query: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class MatchFilters:
    sport: SportCode | None = None
    league_id: str | None = None
    date: date | None = None
    status: MatchStatus | None = None
    limit: int = 50
    offset: int = 0
