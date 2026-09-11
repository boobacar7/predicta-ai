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

EvidenceCategory = Literal["identity", "prediction", "value", "metadata"]
EvidenceAvailability = Literal["available", "unavailable"]

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
class AnalystEvidence:
    """One grounded fact. LLM output is never a source of truth."""

    evidence_id: str
    category: EvidenceCategory
    source_field: str
    value: str | float | None
    source: str
    availability: EvidenceAvailability
    cutoff_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AnalystContext:
    """Immutable whitelist of facts the provider may mention."""

    identity: AnalystIdentity
    prediction: AnalystPrediction
    value: AnalystValue | None
    generated_at: datetime
    data_mode: DataMode
    value_selection: Football1x2Selection | None = None

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
            value_selection=self.value_selection.value if self.value_selection is not None else None,
            odds=float(self.value.odds),
            implied_probability=float(self.value.implied_probability),
            no_vig_probability=float(self.value.no_vig_probability),
            edge=float(self.value.edge),
            ev=float(self.value.ev),
            value_engine_version=self.value.value_engine_version,
            source=self.value.source,
        )

    def evidence(self) -> tuple[AnalystEvidence, ...]:
        """Bounded facts a provider may mention. Narrative is not evidence."""

        identity = self.identity
        prediction = self.prediction
        cutoff = prediction.cutoff_at
        rows: list[tuple[str, EvidenceCategory, str, str | float | None, str, datetime | None]] = [
            ("identity.match_id", "identity", "match_id", identity.match_id, identity.source, None),
            ("identity.home_team", "identity", "home_team", identity.home_team, identity.source, None),
            ("identity.away_team", "identity", "away_team", identity.away_team, identity.source, None),
            ("identity.league", "identity", "league", identity.league, identity.source, None),
            (
                "identity.kickoff_at",
                "identity",
                "kickoff_at",
                identity.kickoff_at.isoformat(),
                identity.source,
                cutoff,
            ),
            (
                "prediction.home_probability",
                "prediction",
                "home_probability",
                float(prediction.home_probability),
                prediction.source,
                cutoff,
            ),
            (
                "prediction.draw_probability",
                "prediction",
                "draw_probability",
                float(prediction.draw_probability),
                prediction.source,
                cutoff,
            ),
            (
                "prediction.away_probability",
                "prediction",
                "away_probability",
                float(prediction.away_probability),
                prediction.source,
                cutoff,
            ),
            (
                "prediction.model_favorite",
                "prediction",
                "model_favorite",
                self.favorite_selection().value,
                prediction.source,
                cutoff,
            ),
            (
                "prediction.model_version",
                "prediction",
                "model_version",
                prediction.model_version,
                prediction.source,
                cutoff,
            ),
            (
                "prediction.model_status",
                "prediction",
                "model_status",
                prediction.model_status,
                prediction.source,
                cutoff,
            ),
            (
                "prediction.dataset_version",
                "prediction",
                "dataset_version",
                prediction.dataset_version,
                prediction.source,
                cutoff,
            ),
            ("metadata.data_mode", "metadata", "data_mode", self.data_mode, IDENTITY_SOURCE, cutoff),
        ]
        if self.value is None:
            rows.extend(
                [
                    ("value.odds", "value", "odds", None, VALUE_SOURCE, cutoff),
                    ("value.edge", "value", "edge", None, VALUE_SOURCE, cutoff),
                    ("value.ev", "value", "ev", None, VALUE_SOURCE, cutoff),
                    ("value.value_selection", "value", "value_selection", None, VALUE_SOURCE, cutoff),
                ]
            )
        else:
            value = self.value
            best_ev = self.value_selection.value if self.value_selection is not None else None
            rows.extend(
                [
                    ("value.selection", "value", "selection", value.selection.value, value.source, cutoff),
                    ("value.value_selection", "value", "value_selection", best_ev, value.source, cutoff),
                    ("value.odds", "value", "odds", float(value.odds), value.source, cutoff),
                    (
                        "value.implied_probability",
                        "value",
                        "implied_probability",
                        float(value.implied_probability),
                        value.source,
                        cutoff,
                    ),
                    (
                        "value.no_vig_probability",
                        "value",
                        "no_vig_probability",
                        float(value.no_vig_probability),
                        value.source,
                        cutoff,
                    ),
                    ("value.edge", "value", "edge", float(value.edge), value.source, cutoff),
                    ("value.ev", "value", "ev", float(value.ev), value.source, cutoff),
                    (
                        "value.odds_age_seconds",
                        "value",
                        "odds_age_seconds",
                        self.odds_age_seconds(),
                        value.odds_source,
                        cutoff,
                    ),
                    (
                        "value.value_engine_version",
                        "value",
                        "value_engine_version",
                        value.value_engine_version,
                        value.source,
                        cutoff,
                    ),
                ]
            )
        return tuple(_fact(*row) for row in rows)


def _fact(
    evidence_id: str,
    category: EvidenceCategory,
    source_field: str,
    value: str | float | None,
    source: str,
    cutoff_at: datetime | None = None,
) -> AnalystEvidence:
    available = value is not None
    return AnalystEvidence(
        evidence_id=evidence_id,
        category=category,
        source_field=source_field,
        value=value,
        source=source,
        availability="available" if available else "unavailable",
        cutoff_at=cutoff_at,
    )


def highest_ev_selection(analysis: FootballValueAnalysis) -> Football1x2Selection:
    evs = {
        Football1x2Selection.HOME: Decimal(str(analysis.value.home.ev)),
        Football1x2Selection.DRAW: Decimal(str(analysis.value.draw.ev)),
        Football1x2Selection.AWAY: Decimal(str(analysis.value.away.ev)),
    }
    return sorted(
        SELECTION_TIEBREAK,
        key=lambda selection: (-evs[selection], SELECTION_TIEBREAK.index(selection)),
    )[0]


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
