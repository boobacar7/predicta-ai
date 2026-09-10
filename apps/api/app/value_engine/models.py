from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_serializer

from app.core.clock import to_rfc3339
from app.schemas import ApiModel, DataMode, FootballModelStatus


class ValuePrediction(ApiModel):
    home_probability: float = Field(gt=0, lt=1)
    draw_probability: float = Field(gt=0, lt=1)
    away_probability: float = Field(gt=0, lt=1)


class ValueOdds(ApiModel):
    bookmaker: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    home_odds: float = Field(gt=1)
    draw_odds: float = Field(gt=1)
    away_odds: float = Field(gt=1)
    collected_at: datetime
    available_at: datetime

    @field_serializer("collected_at", "available_at")
    def _timestamps(self, value: datetime) -> str:
        return to_rfc3339(value)


class SelectionMarketProbabilities(ApiModel):
    implied_probability: float = Field(gt=0, lt=1)
    no_vig_probability: float = Field(gt=0, lt=1)


class ValueMarket(ApiModel):
    overround: float = Field(gt=0)
    home: SelectionMarketProbabilities
    draw: SelectionMarketProbabilities
    away: SelectionMarketProbabilities


class SelectionValue(ApiModel):
    edge: float = Field(gt=-1, lt=1)
    ev: float = Field(ge=-1)


class ValueBySelection(ApiModel):
    home: SelectionValue
    draw: SelectionValue
    away: SelectionValue


class ValueMetadata(ApiModel):
    value_engine_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    model_status: FootballModelStatus
    dataset_version: str = Field(min_length=1)
    feature_schema_version: str = Field(min_length=1)
    odds_source: str = Field(min_length=1)
    cutoff_at: datetime
    generated_at: datetime
    data_mode: DataMode

    @field_serializer("cutoff_at", "generated_at")
    def _timestamps(self, value: datetime) -> str:
        return to_rfc3339(value)


class FootballValueAnalysis(ApiModel):
    match_id: str = Field(min_length=1, max_length=128)
    sport: Literal["football"] = "football"
    market: Literal["1X2"] = "1X2"
    prediction: ValuePrediction
    odds: ValueOdds
    market_probabilities: ValueMarket
    value: ValueBySelection
    metadata: ValueMetadata
