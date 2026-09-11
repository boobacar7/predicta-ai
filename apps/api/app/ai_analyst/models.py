from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import Field, field_serializer

from app.core.clock import to_rfc3339
from app.odds.types import DataMode, Football1x2Selection
from app.schemas import ApiModel, FootballModelStatus, FreshnessLevel

ANALYST_VERSION: Final[Literal["ai-analyst-0.1"]] = "ai-analyst-0.1"
ANALYST_PROVIDER_ID: Final[Literal["deterministic-v0.1"]] = "deterministic-v0.1"
PREDICTION_SOURCE = "football-prediction-service"
VALUE_SOURCE = "value-engine-0.1"
IDENTITY_SOURCE = "match-identity-repository"
CONFIDENCE_RULE = (
    "high requires champion + live + complete identity + available value; "
    "candidate with complete identity and available value is medium; "
    "any of candidate+gap, mock, missing value, or incomplete identity is low; "
    "probability magnitude is never used."
)

AnalystAvailability = Literal["available", "unavailable"]
ContextAvailability = Literal["available", "partial", "unavailable"]
ConfidenceLevel = Literal["low", "medium", "high"]
FactorType = Literal[
    "model_probability",
    "market_probability",
    "edge",
    "ev",
    "data_freshness",
    "model_status",
]
FactorDirection = Literal["home", "away", "draw", "neutral"]


class FootballAnalystFactor(ApiModel):
    type: FactorType
    label: str = Field(min_length=1)
    value: float | None = None
    direction: FactorDirection | None = None
    source: str = Field(min_length=1)


class FootballAnalystPrediction(ApiModel):
    home_probability: float = Field(gt=0, lt=1)
    draw_probability: float = Field(gt=0, lt=1)
    away_probability: float = Field(gt=0, lt=1)
    model_version: str = Field(min_length=1)
    model_status: FootballModelStatus
    dataset_version: str = Field(min_length=1)
    cutoff_at: datetime
    source: str = Field(min_length=1)

    @field_serializer("cutoff_at")
    def _cutoff(self, value: datetime) -> str:
        return to_rfc3339(value)


class FootballAnalystValue(ApiModel):
    availability: AnalystAvailability
    selection: Literal["HOME", "DRAW", "AWAY"] | None = None
    odds: float | None = Field(default=None, gt=1)
    implied_probability: float | None = Field(default=None, gt=0, lt=1)
    no_vig_probability: float | None = Field(default=None, gt=0, lt=1)
    edge: float | None = Field(default=None, gt=-1, lt=1)
    ev: float | None = Field(default=None, ge=-1)
    value_engine_version: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, min_length=1)


class FootballAnalystConfidence(ApiModel):
    level: ConfidenceLevel
    basis: str = Field(min_length=1)
    rule: str = Field(min_length=1)


class FootballAnalystDataQuality(ApiModel):
    data_mode: DataMode
    model_status: FootballModelStatus
    cutoff_at: datetime
    freshness: FreshnessLevel | None
    availability: ContextAvailability
    missing: list[str]

    @field_serializer("cutoff_at")
    def _cutoff(self, value: datetime) -> str:
        return to_rfc3339(value)


class FootballAnalystExplanation(ApiModel):
    summary: str = Field(min_length=1)
    key_factors: list[FootballAnalystFactor]
    strengths: list[str]
    risks: list[str]
    confidence: FootballAnalystConfidence
    data_quality: FootballAnalystDataQuality
    generated_at: datetime
    analysis_version: Literal["ai-analyst-0.1"] = ANALYST_VERSION
    provider: Literal["deterministic-v0.1"] = ANALYST_PROVIDER_ID

    @field_serializer("generated_at")
    def _generated(self, value: datetime) -> str:
        return to_rfc3339(value)


class FootballAiAnalystReport(ApiModel):
    match_id: str = Field(min_length=1, max_length=128)
    home_team: str | None = Field(default=None, min_length=1)
    away_team: str | None = Field(default=None, min_length=1)
    league: str = Field(min_length=1)
    kickoff_at: datetime
    prediction: FootballAnalystPrediction
    value: FootballAnalystValue
    analyst: FootballAnalystExplanation

    @field_serializer("kickoff_at")
    def _kickoff(self, value: datetime) -> str:
        return to_rfc3339(value)


def selection_direction(selection: Football1x2Selection) -> FactorDirection:
    mapping: dict[Football1x2Selection, FactorDirection] = {
        Football1x2Selection.HOME: "home",
        Football1x2Selection.DRAW: "draw",
        Football1x2Selection.AWAY: "away",
    }
    return mapping[selection]
