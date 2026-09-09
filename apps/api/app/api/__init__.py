from datetime import date
from typing import Annotated

from fastapi import Query

from app.schemas import MatchStatus, SportCode

LimitQuery = Annotated[int, Query(ge=1, le=100)]
OffsetQuery = Annotated[int, Query(ge=0)]
SearchQuery = Annotated[str | None, Query(min_length=1, max_length=100)]
MarketQuery = Annotated[str | None, Query(min_length=1, max_length=64)]
SportQuery = Annotated[SportCode | None, Query()]
StatusQuery = Annotated[MatchStatus | None, Query()]
DateQuery = Annotated[date | None, Query()]
LeagueIdQuery = Annotated[str | None, Query(min_length=1, max_length=128)]
