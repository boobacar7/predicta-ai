from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from predicta_ingestion.canonical.enums import (
    Availability,
    DataMode,
    Freshness,
    InjuryStatus,
    LineupRole,
    MatchStatus,
    SportCode,
)
from predicta_ingestion.clock import NaiveDateTimeError, ensure_utc


def _require_utc(value: datetime) -> datetime:
    try:
        return ensure_utc(value)
    except NaiveDateTimeError as exc:
        raise ValueError(str(exc)) from exc


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=128)
    provider_id: str = Field(min_length=1, max_length=255)
    collected_at: datetime
    available_at: datetime
    source: str = Field(min_length=1, max_length=128)
    data_mode: DataMode
    event_at: datetime | None = None
    freshness: Freshness | None = None
    raw_payload_id: str | None = None

    @field_validator("collected_at", "available_at", "event_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        return _require_utc(value)


class Sport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: SportCode
    name: str
    provenance: Provenance


class League(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sport_id: str
    name: str
    country: str
    season: str
    tier: int = 1
    provenance: Provenance


class Team(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sport_id: str
    league_id: str
    name: str
    short_name: str
    abbreviation: str = Field(max_length=12)
    provenance: Provenance


class Player(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sport_id: str
    name: str
    country: str
    team_id: str | None = None
    position: str | None = None
    provenance: Provenance


class Match(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sport_id: str
    league_id: str
    kickoff_at: datetime
    status: MatchStatus
    home_team_id: str | None = None
    away_team_id: str | None = None
    home_player_id: str | None = None
    away_player_id: str | None = None
    venue: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    surface: str | None = None
    natural_key: str | None = None
    provenance: Provenance

    @field_validator("kickoff_at")
    @classmethod
    def kickoff_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @model_validator(mode="after")
    def participants_match_sport(self) -> Self:
        if self.sport_id == SportCode.TENNIS or self.sport_id.endswith(SportCode.TENNIS.value):
            if self.home_player_id is None or self.away_player_id is None:
                raise ValueError("Tennis matches require home_player_id and away_player_id.")
        elif self.home_team_id is None or self.away_team_id is None:
            raise ValueError("Team-sport matches require home_team_id and away_team_id.")
        if self.status is MatchStatus.FINISHED and (self.home_score is None or self.away_score is None):
            raise ValueError("Finished matches must include scores; missing scores are not zero.")
        return self


class MatchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    match_id: str
    event_type: str
    label: str
    minute: int | None = None
    team_id: str | None = None
    player_id: str | None = None
    provenance: Provenance


class TeamStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str
    season: str
    stat_key: str
    label: str
    availability: Availability
    as_of: datetime
    value: Decimal | None = None
    unit: str | None = None
    provenance: Provenance

    @field_validator("as_of")
    @classmethod
    def as_of_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @model_validator(mode="after")
    def missing_is_not_zero(self) -> Self:
        if self.availability is Availability.UNAVAILABLE and self.value is not None:
            raise ValueError("Unavailable statistics must have a null value, never 0.")
        return self


class PlayerStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    season: str
    stat_key: str
    label: str
    availability: Availability
    as_of: datetime
    value: Decimal | None = None
    unit: str | None = None
    provenance: Provenance

    @field_validator("as_of")
    @classmethod
    def as_of_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @model_validator(mode="after")
    def missing_is_not_zero(self) -> Self:
        if self.availability is Availability.UNAVAILABLE and self.value is not None:
            raise ValueError("Unavailable statistics must have a null value, never 0.")
        return self


class OddsSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: str
    label: str
    decimal_odds: Decimal

    @field_validator("decimal_odds")
    @classmethod
    def odds_strictly_above_one(cls, value: Decimal) -> Decimal:
        if value <= 1:
            raise ValueError("Decimal odds must be strictly greater than 1.")
        return value


class OddsSnapshot(BaseModel):
    """Raw priced snapshot. Implied probability and EV are Value Engine concerns."""

    model_config = ConfigDict(extra="forbid")

    id: str
    match_id: str
    market: str
    bookmaker: str
    selections: list[OddsSelection]
    provenance: Provenance
    match_natural_key: str | None = None

    @model_validator(mode="after")
    def selections_present(self) -> Self:
        if not self.selections:
            raise ValueError("An odds snapshot must contain at least one selection.")
        return self


class StandingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    league_id: str
    season: str
    team_id: str
    availability: Availability
    as_of: datetime
    rank: int | None = None
    points: int | None = None
    played: int | None = None
    won: int | None = None
    drawn: int | None = None
    lost: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    provenance: Provenance

    @field_validator("as_of")
    @classmethod
    def as_of_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


class Injury(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sport_id: str
    status: InjuryStatus
    availability: Availability
    provenance: Provenance
    player_id: str | None = None
    team_id: str | None = None
    description: str | None = None


class LineupPlayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: LineupRole
    player_id: str | None = None
    jersey_number: int | None = None
    position: str | None = None


class Lineup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    match_id: str
    team_id: str
    availability: Availability
    provenance: Provenance
    formation: str | None = None
    players: list[LineupPlayer] = Field(default_factory=list)


class CanonicalBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sports: list[Sport] = Field(default_factory=list)
    leagues: list[League] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    players: list[Player] = Field(default_factory=list)
    matches: list[Match] = Field(default_factory=list)
    events: list[MatchEvent] = Field(default_factory=list)
    team_stats: list[TeamStats] = Field(default_factory=list)
    player_stats: list[PlayerStats] = Field(default_factory=list)
    odds: list[OddsSnapshot] = Field(default_factory=list)
    standings: list[StandingSnapshot] = Field(default_factory=list)
    injuries: list[Injury] = Field(default_factory=list)
    lineups: list[Lineup] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            (
                self.sports,
                self.leagues,
                self.teams,
                self.players,
                self.matches,
                self.events,
                self.team_stats,
                self.player_stats,
                self.odds,
                self.standings,
                self.injuries,
                self.lineups,
            )
        )
