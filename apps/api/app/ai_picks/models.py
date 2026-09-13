from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_serializer

from app.core.clock import to_rfc3339
from app.match_identity.models import MatchIdentity
from app.odds.types import DataMode, Football1x2Selection
from app.schemas import ApiModel, FootballModelStatus


class OpportunityStatus(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED = "excluded"


class ExclusionReason(StrEnum):
    NEGATIVE_EV = "negative_ev"
    NEGATIVE_EDGE = "negative_edge"
    BELOW_MINIMUM_EV = "below_minimum_ev"
    BELOW_MINIMUM_EDGE = "below_minimum_edge"
    BELOW_MINIMUM_MODEL_PROBABILITY = "below_minimum_model_probability"
    INVALID_ODDS = "invalid_odds"
    INCOMPLETE_MARKET = "incomplete_market"
    PREDICTION_UNAVAILABLE = "prediction_unavailable"
    PIT_UNAVAILABLE = "pit_unavailable"
    INVALID_PREDICTION = "invalid_prediction"
    INVALID_VALUE = "invalid_value"
    STALE_ODDS = "stale_odds"


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    match_id: str
    home_team_id: str
    away_team_id: str
    home_team: str | None
    away_team: str | None
    league: str
    kickoff_at: datetime

    @classmethod
    def from_identity(cls, identity: MatchIdentity) -> MatchCandidate:
        return cls(
            match_id=identity.match_id,
            home_team_id=identity.home_team_id,
            away_team_id=identity.away_team_id,
            home_team=identity.home_team,
            away_team=identity.away_team,
            league=identity.league,
            kickoff_at=identity.kickoff_at,
        )


@dataclass(frozen=True, slots=True)
class Opportunity:
    match_id: str
    sport: str
    home_team: str | None
    away_team: str | None
    league: str
    kickoff_at: datetime
    market: str
    selection: Football1x2Selection
    model_probability: Decimal
    implied_probability: Decimal
    no_vig_probability: Decimal
    edge: Decimal
    ev: Decimal
    odds: Decimal
    odds_source: str
    model_version: str
    model_status: FootballModelStatus
    value_engine_version: str
    cutoff_at: datetime
    generated_at: datetime
    data_mode: DataMode
    odds_available_at: datetime
    data_freshness: int
    opportunity_score: Decimal


class AiPick(ApiModel):
    match_id: str = Field(min_length=1, max_length=128)
    sport: Literal["football"] = "football"
    home_team: str | None = Field(min_length=1)
    away_team: str | None = Field(min_length=1)
    league: str = Field(min_length=1)
    kickoff_at: datetime
    market: Literal["1X2"] = "1X2"
    selection: Literal["HOME", "DRAW", "AWAY"]
    model_probability: float = Field(gt=0, lt=1)
    odds: float = Field(gt=1)
    implied_probability: float = Field(gt=0, lt=1)
    no_vig_probability: float = Field(gt=0, lt=1)
    edge: float = Field(gt=-1, lt=1)
    ev: float = Field(ge=-1)
    opportunity_score: float
    rank: int = Field(ge=1)
    odds_source: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    model_status: FootballModelStatus
    value_engine_version: str = Field(min_length=1)
    ai_picks_version: Literal["ai-picks-0.1"] = "ai-picks-0.1"
    cutoff_at: datetime
    generated_at: datetime
    data_mode: DataMode
    status: Literal["eligible"] = "eligible"

    @field_serializer("kickoff_at", "cutoff_at", "generated_at")
    def _timestamps(self, value: datetime) -> str:
        return to_rfc3339(value)


class AiPickExclusion(ApiModel):
    match_id: str = Field(min_length=1, max_length=128)
    league: str = Field(min_length=1)
    market: Literal["1X2"] = "1X2"
    selection: Literal["HOME", "DRAW", "AWAY"] | None = None
    status: Literal["excluded"] = "excluded"
    reason: ExclusionReason
    detail: str = Field(min_length=1)


class AiPicksMetadata(ApiModel):
    ai_picks_version: Literal["ai-picks-0.1"] = "ai-picks-0.1"
    scoring_formula: Literal["opportunity_score = EV + Edge"] = "opportunity_score = EV + Edge"
    ranking_order: str = "score DESC, EV DESC, edge DESC, freshness DESC, match_id ASC, selection ASC"
    minimum_edge: float
    minimum_ev: float
    minimum_model_probability: float
    maximum_odds_age_seconds: int = Field(gt=0)
    evaluated_matches: int = Field(ge=0)
    eligible_opportunities: int = Field(ge=0)
    excluded_opportunities: int = Field(ge=0)
    candidate_model_allowed: bool = True


class AiPicksResult(ApiModel):
    items: list[AiPick]
    exclusions: list[AiPickExclusion]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    metadata: AiPicksMetadata


@dataclass(frozen=True, slots=True)
class AiPicksQuery:
    match_date: date | None
    league: str | None
    limit: int
    offset: int
    minimum_edge: Decimal | None
    minimum_ev: Decimal | None
