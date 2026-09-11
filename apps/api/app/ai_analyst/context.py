from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.ai_analyst.models import (
    IDENTITY_SOURCE,
    PREDICTION_SOURCE,
    VALUE_SOURCE,
    FootballAnalystPrediction,
    FootballAnalystValue,
)
from app.odds.types import DataMode, Football1x2Selection
from app.schemas import FootballModelStatus, FreshnessLevel
from app.value_engine.calculator import VALUE_ENGINE_VERSION
from app.value_engine.models import FootballValueAnalysis

FRESH_ODDS_SECONDS = 12 * 3600
ACCEPTABLE_ODDS_SECONDS = 24 * 3600
SELECTION_TIEBREAK = (
    Football1x2Selection.HOME,
    Football1x2Selection.DRAW,
    Football1x2Selection.AWAY,
)


@dataclass(frozen=True, slots=True)
class AnalystIdentity:
    match_id: str
    home_team: str | None
    away_team: str | None
    league: str
    kickoff_at: datetime
    source: str = IDENTITY_SOURCE


@dataclass(frozen=True, slots=True)
class AnalystPrediction:
    home_probability: Decimal
    draw_probability: Decimal
    away_probability: Decimal
    model_version: str
    model_status: FootballModelStatus
    dataset_version: str
    cutoff_at: datetime
    source: str = PREDICTION_SOURCE

    def probability(self, selection: Football1x2Selection) -> Decimal:
        return {
            Football1x2Selection.HOME: self.home_probability,
            Football1x2Selection.DRAW: self.draw_probability,
            Football1x2Selection.AWAY: self.away_probability,
        }[selection]

    def favorite_selection(self) -> Football1x2Selection:
        return sorted(
            SELECTION_TIEBREAK,
            key=lambda selection: (-self.probability(selection), SELECTION_TIEBREAK.index(selection)),
        )[0]


@dataclass(frozen=True, slots=True)
class AnalystValue:
    selection: Football1x2Selection
    odds: Decimal
    implied_probability: Decimal
    no_vig_probability: Decimal
    edge: Decimal
    ev: Decimal
    value_engine_version: str
    odds_available_at: datetime
    odds_source: str
    data_mode: DataMode
    source: str = VALUE_SOURCE


@dataclass(frozen=True, slots=True)
class AnalystContext:
    """Immutable whitelist of facts the provider may mention."""

    identity: AnalystIdentity
    prediction: AnalystPrediction
    value: AnalystValue | None
    generated_at: datetime
    data_mode: DataMode

    def favorite_selection(self) -> Football1x2Selection:
        return self.prediction.favorite_selection()

    def missing(self) -> tuple[str, ...]:
        gaps: list[str] = []
        if self.identity.home_team is None:
            gaps.append("home_team")
        if self.identity.away_team is None:
            gaps.append("away_team")
        if self.value is None:
            gaps.append("odds")
            gaps.append("value")
        return tuple(gaps)

    def identity_complete(self) -> bool:
        return self.identity.home_team is not None and self.identity.away_team is not None

    def odds_age_seconds(self) -> float | None:
        if self.value is None:
            return None
        return (self.prediction.cutoff_at - self.value.odds_available_at).total_seconds()

    def freshness(self) -> FreshnessLevel | None:
        age = self.odds_age_seconds()
        if age is None:
            return None
        if age <= FRESH_ODDS_SECONDS:
            return "fresh"
        if age <= ACCEPTABLE_ODDS_SECONDS:
            return "acceptable"
        return "stale"

    def context_availability(self) -> Literal["available", "partial"]:
        if self.missing():
            return "partial"
        return "available"

    def to_prediction_dto(self) -> FootballAnalystPrediction:
        return FootballAnalystPrediction(
            home_probability=float(self.prediction.home_probability),
            draw_probability=float(self.prediction.draw_probability),
            away_probability=float(self.prediction.away_probability),
            model_version=self.prediction.model_version,
            model_status=self.prediction.model_status,
            dataset_version=self.prediction.dataset_version,
            cutoff_at=self.prediction.cutoff_at,
            source=self.prediction.source,
        )

    def to_value_dto(self) -> FootballAnalystValue:
        if self.value is None:
            return FootballAnalystValue(availability="unavailable")
        return FootballAnalystValue(
            availability="available",
            selection=self.value.selection.value,
            odds=float(self.value.odds),
            implied_probability=float(self.value.implied_probability),
            no_vig_probability=float(self.value.no_vig_probability),
            edge=float(self.value.edge),
            ev=float(self.value.ev),
            value_engine_version=self.value.value_engine_version,
            source=self.value.source,
        )


def value_for_selection(analysis: FootballValueAnalysis, selection: Football1x2Selection) -> AnalystValue:
    if analysis.metadata.value_engine_version != VALUE_ENGINE_VERSION:
        raise ValueError("Value Engine version is incompatible with ai-analyst-0.1.")
    odds = {
        Football1x2Selection.HOME: Decimal(str(analysis.odds.home_odds)),
        Football1x2Selection.DRAW: Decimal(str(analysis.odds.draw_odds)),
        Football1x2Selection.AWAY: Decimal(str(analysis.odds.away_odds)),
    }
    markets = {
        Football1x2Selection.HOME: analysis.market_probabilities.home,
        Football1x2Selection.DRAW: analysis.market_probabilities.draw,
        Football1x2Selection.AWAY: analysis.market_probabilities.away,
    }
    values = {
        Football1x2Selection.HOME: analysis.value.home,
        Football1x2Selection.DRAW: analysis.value.draw,
        Football1x2Selection.AWAY: analysis.value.away,
    }
    market = markets[selection]
    selected = values[selection]
    return AnalystValue(
        selection=selection,
        odds=odds[selection],
        implied_probability=Decimal(str(market.implied_probability)),
        no_vig_probability=Decimal(str(market.no_vig_probability)),
        edge=Decimal(str(selected.edge)),
        ev=Decimal(str(selected.ev)),
        value_engine_version=analysis.metadata.value_engine_version,
        odds_available_at=analysis.odds.available_at,
        odds_source=analysis.metadata.odds_source,
        data_mode=analysis.metadata.data_mode,
    )
