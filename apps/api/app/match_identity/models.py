from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import Field, field_serializer

from app.core.clock import to_rfc3339
from app.schemas import ApiModel, DataMode


@dataclass(frozen=True, slots=True)
class MatchIdentity:
    """Structural identity only; no result, status, score, or match event."""

    match_id: str
    home_team_id: str
    away_team_id: str
    home_team: str | None
    away_team: str | None
    league: str
    kickoff_at: datetime
    data_mode: DataMode


class HistoricalMatchIdentity(ApiModel):
    """Partial resource returned for canonical historical matches outside the UI repository."""

    match_id: str = Field(min_length=1, max_length=128)
    home_team_id: str = Field(min_length=1, max_length=128)
    away_team_id: str = Field(min_length=1, max_length=128)
    home_team: str | None = Field(min_length=1)
    away_team: str | None = Field(min_length=1)
    league: str = Field(min_length=1)
    kickoff_at: datetime
    data_mode: DataMode
    resource_scope: str = "structural_identity"

    @field_serializer("kickoff_at")
    def _kickoff(self, value: datetime) -> str:
        return to_rfc3339(value)

    @classmethod
    def from_identity(cls, identity: MatchIdentity) -> HistoricalMatchIdentity:
        return cls(
            match_id=identity.match_id,
            home_team_id=identity.home_team_id,
            away_team_id=identity.away_team_id,
            home_team=identity.home_team,
            away_team=identity.away_team,
            league=identity.league,
            kickoff_at=identity.kickoff_at,
            data_mode=identity.data_mode,
        )
