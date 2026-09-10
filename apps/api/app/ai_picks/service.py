from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.ai_picks.models import (
    AiPick,
    AiPickExclusion,
    AiPicksMetadata,
    AiPicksQuery,
    AiPicksResult,
    ExclusionReason,
    MatchCandidate,
    Opportunity,
)
from app.odds.exceptions import IncompleteOddsMarketError, OddsTemporalLeakageError, OddsUnavailableError
from app.odds.types import FOOTBALL_1X2_MARKET, Football1x2Selection
from app.predictions.exceptions import PitFeaturesUnavailableError, TemporalLeakageError
from app.value_engine import calculator
from app.value_engine.calculator import VALUE_ENGINE_VERSION
from app.value_engine.exceptions import InvalidPredictionError
from app.value_engine.models import FootballValueAnalysis, SelectionValue


class ValueService(Protocol):
    def evaluate(self, match_id: str, cutoff_at: datetime | None) -> FootballValueAnalysis: ...


class MatchCandidateSource(Protocol):
    def list_candidates(self, *, match_date: date | None, league: str | None) -> list[MatchCandidate]: ...


class AiPicksEngine:
    """Filter and rank Value Engine outputs; never computes model probabilities."""

    def __init__(
        self,
        *,
        values: ValueService,
        candidates: MatchCandidateSource,
        thresholds: AiPicksThresholds,
    ) -> None:
        self._values = values
        self._candidates = candidates
        self._thresholds = thresholds

    def list_picks(self, query: AiPicksQuery) -> AiPicksResult:
        thresholds = self._effective_thresholds(query)
        discovered = self._candidates.list_candidates(match_date=query.match_date, league=query.league)
        candidates = sorted(
            {item.match_id: item for item in discovered}.values(),
            key=lambda item: item.match_id,
        )
        eligible: list[Opportunity] = []
        exclusions: list[AiPickExclusion] = []
        for candidate in candidates:
            try:
                analysis = self._values.evaluate(candidate.match_id, candidate.kickoff_at)
                opportunities, rejected = self._evaluate_analysis(candidate, analysis, thresholds)
                eligible.extend(opportunities)
                exclusions.extend(rejected)
            except Exception as exc:
                reason = self._pipeline_exclusion(exc)
                if reason is None:
                    raise
                exclusions.append(
                    AiPickExclusion(
                        match_id=candidate.match_id,
                        league=candidate.league,
                        reason=reason,
                        detail=str(exc),
                    )
                )

        ranked = self._rank_opportunities(eligible)
        items = [self._to_pick(item, rank=index + 1) for index, item in enumerate(ranked)]
        page = items[query.offset : query.offset + query.limit]
        return AiPicksResult(
            items=page,
            exclusions=exclusions,
            total=len(items),
            limit=query.limit,
            offset=query.offset,
            metadata=AiPicksMetadata(
                minimum_edge=float(thresholds.minimum_edge),
                minimum_ev=float(thresholds.minimum_ev),
                minimum_model_probability=float(thresholds.minimum_model_probability),
                maximum_odds_age_seconds=int(thresholds.maximum_odds_age.total_seconds()),
                evaluated_matches=len(candidates),
                eligible_opportunities=len(items),
                excluded_opportunities=len(exclusions),
            ),
        )

    @staticmethod
    def _rank_opportunities(items: list[Opportunity]) -> list[Opportunity]:
        return sorted(
            items,
            key=lambda item: (
                -item.opportunity_score,
                -item.ev,
                -item.edge,
                -item.data_freshness,
                item.match_id,
                item.selection.value,
            ),
        )

    def _evaluate_analysis(
        self,
        candidate: MatchCandidate,
        analysis: FootballValueAnalysis,
        thresholds: AiPicksThresholds,
    ) -> tuple[list[Opportunity], list[AiPickExclusion]]:
        self._validate_analysis(candidate, analysis)
        age = analysis.metadata.cutoff_at - analysis.odds.available_at
        if age.total_seconds() < 0:
            raise OddsTemporalLeakageError("Odds available_at is after the canonical prediction cutoff.")
        freshness = 2 if age <= thresholds.maximum_odds_age / 2 else 1
        odds_by_selection = {
            Football1x2Selection.HOME: Decimal(str(analysis.odds.home_odds)),
            Football1x2Selection.DRAW: Decimal(str(analysis.odds.draw_odds)),
            Football1x2Selection.AWAY: Decimal(str(analysis.odds.away_odds)),
        }
        probabilities = {
            Football1x2Selection.HOME: Decimal(str(analysis.prediction.home_probability)),
            Football1x2Selection.DRAW: Decimal(str(analysis.prediction.draw_probability)),
            Football1x2Selection.AWAY: Decimal(str(analysis.prediction.away_probability)),
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
        eligible: list[Opportunity] = []
        excluded: list[AiPickExclusion] = []
        for selection in Football1x2Selection:
            reason = self._selection_exclusion(
                probability=probabilities[selection],
                value=values[selection],
                age_seconds=age.total_seconds(),
                thresholds=thresholds,
            )
            if reason is not None:
                excluded.append(
                    AiPickExclusion(
                        match_id=candidate.match_id,
                        league=candidate.league,
                        selection=selection.value,
                        reason=reason,
                        detail=self._exclusion_detail(reason),
                    )
                )
                continue
            market = markets[selection]
            edge = Decimal(str(values[selection].edge))
            ev = Decimal(str(values[selection].ev))
            eligible.append(
                Opportunity(
                    match_id=candidate.match_id,
                    sport=analysis.sport,
                    league=candidate.league,
                    market=analysis.market,
                    selection=selection,
                    model_probability=probabilities[selection],
                    implied_probability=Decimal(str(market.implied_probability)),
                    no_vig_probability=Decimal(str(market.no_vig_probability)),
                    edge=edge,
                    ev=ev,
                    odds=odds_by_selection[selection],
                    odds_source=analysis.metadata.odds_source,
                    model_version=analysis.metadata.model_version,
                    model_status=analysis.metadata.model_status,
                    value_engine_version=analysis.metadata.value_engine_version,
                    cutoff_at=analysis.metadata.cutoff_at,
                    generated_at=analysis.metadata.generated_at,
                    data_mode=analysis.metadata.data_mode,
                    odds_available_at=analysis.odds.available_at,
                    data_freshness=freshness,
                    opportunity_score=ev + edge,
                )
            )
        return eligible, excluded

    @staticmethod
    def _validate_analysis(candidate: MatchCandidate, analysis: FootballValueAnalysis) -> None:
        if analysis.match_id != candidate.match_id or analysis.sport != "football":
            raise InvalidPredictionError("Value analysis identity is inconsistent with the candidate match.")
        if analysis.market != FOOTBALL_1X2_MARKET:
            raise IncompleteOddsMarketError("AI Picks V0.1 only supports complete football 1X2 markets.")
        probability_sum = (
            Decimal(str(analysis.prediction.home_probability))
            + Decimal(str(analysis.prediction.draw_probability))
            + Decimal(str(analysis.prediction.away_probability))
        )
        if abs(probability_sum - Decimal(1)) > Decimal("0.000000001"):
            raise InvalidPredictionError("Prediction probabilities must sum to 1.")
        if not analysis.metadata.model_status:
            raise InvalidPredictionError("Prediction model_status is missing.")
        if analysis.metadata.value_engine_version != VALUE_ENGINE_VERSION:
            raise ValueError("Value Engine version is incompatible with AI Picks V0.1.")
        if analysis.metadata.cutoff_at != candidate.kickoff_at:
            raise TemporalLeakageError("Value analysis did not preserve the canonical prediction cutoff.")
        if analysis.odds.available_at > analysis.metadata.cutoff_at:
            raise OddsTemporalLeakageError("Odds became available after the canonical cutoff.")
        odds = {
            Football1x2Selection.HOME: Decimal(str(analysis.odds.home_odds)),
            Football1x2Selection.DRAW: Decimal(str(analysis.odds.draw_odds)),
            Football1x2Selection.AWAY: Decimal(str(analysis.odds.away_odds)),
        }
        probabilities = {
            Football1x2Selection.HOME: Decimal(str(analysis.prediction.home_probability)),
            Football1x2Selection.DRAW: Decimal(str(analysis.prediction.draw_probability)),
            Football1x2Selection.AWAY: Decimal(str(analysis.prediction.away_probability)),
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
        no_vig, overround = calculator.no_vig_probabilities(odds)
        tolerance = Decimal("0.000000001")
        if abs(Decimal(str(analysis.market_probabilities.overround)) - overround) > tolerance:
            raise ValueError("Value analysis contains an inconsistent market overround.")
        for selection in Football1x2Selection:
            implied = calculator.implied_probability(odds[selection])
            expected_edge = calculator.edge(probabilities[selection], implied)
            expected_ev = calculator.expected_value(probabilities[selection], odds[selection])
            market = markets[selection]
            value = values[selection]
            if (
                abs(Decimal(str(market.implied_probability)) - implied) > tolerance
                or abs(Decimal(str(market.no_vig_probability)) - no_vig[selection]) > tolerance
                or abs(Decimal(str(value.edge)) - expected_edge) > tolerance
                or abs(Decimal(str(value.ev)) - expected_ev) > tolerance
            ):
                raise ValueError("Value analysis contains inconsistent calculations.")

    @staticmethod
    def _selection_exclusion(
        *,
        probability: Decimal,
        value: SelectionValue,
        age_seconds: float,
        thresholds: AiPicksThresholds,
    ) -> ExclusionReason | None:
        edge = Decimal(str(value.edge))
        ev = Decimal(str(value.ev))
        if age_seconds > thresholds.maximum_odds_age.total_seconds():
            return ExclusionReason.STALE_ODDS
        if probability < thresholds.minimum_model_probability:
            return ExclusionReason.BELOW_MINIMUM_MODEL_PROBABILITY
        if ev < 0:
            return ExclusionReason.NEGATIVE_EV
        if ev < thresholds.minimum_ev:
            return ExclusionReason.BELOW_MINIMUM_EV
        if edge < 0:
            return ExclusionReason.NEGATIVE_EDGE
        if edge < thresholds.minimum_edge:
            return ExclusionReason.BELOW_MINIMUM_EDGE
        return None

    @staticmethod
    def _pipeline_exclusion(exc: Exception) -> ExclusionReason | None:
        if isinstance(exc, IncompleteOddsMarketError):
            return ExclusionReason.INCOMPLETE_MARKET
        if isinstance(exc, OddsUnavailableError):
            return ExclusionReason.INVALID_ODDS
        if isinstance(exc, (OddsTemporalLeakageError, TemporalLeakageError)):
            return ExclusionReason.PIT_UNAVAILABLE
        if isinstance(exc, PitFeaturesUnavailableError):
            return ExclusionReason.PREDICTION_UNAVAILABLE
        if isinstance(exc, InvalidPredictionError):
            return ExclusionReason.INVALID_PREDICTION
        if isinstance(exc, (ValueError, ArithmeticError)):
            return ExclusionReason.INVALID_VALUE
        return None

    @staticmethod
    def _exclusion_detail(reason: ExclusionReason) -> str:
        return {
            ExclusionReason.NEGATIVE_EV: "Expected value is negative.",
            ExclusionReason.NEGATIVE_EDGE: "Model edge is negative.",
            ExclusionReason.BELOW_MINIMUM_EV: "Expected value is below the configured minimum.",
            ExclusionReason.BELOW_MINIMUM_EDGE: "Model edge is below the configured minimum.",
            ExclusionReason.BELOW_MINIMUM_MODEL_PROBABILITY: (
                "Model probability is below the configured minimum."
            ),
            ExclusionReason.STALE_ODDS: "Odds are older than the configured maximum age.",
        }[reason]

    def _effective_thresholds(self, query: AiPicksQuery) -> AiPicksThresholds:
        return self._thresholds.model_copy(
            update={
                "minimum_edge": query.minimum_edge
                if query.minimum_edge is not None
                else self._thresholds.minimum_edge,
                "minimum_ev": query.minimum_ev if query.minimum_ev is not None else self._thresholds.minimum_ev,
            }
        )

    @staticmethod
    def _to_pick(item: Opportunity, *, rank: int) -> AiPick:
        return AiPick(
            match_id=item.match_id,
            league=item.league,
            selection=item.selection.value,
            model_probability=float(item.model_probability),
            odds=float(item.odds),
            implied_probability=float(item.implied_probability),
            no_vig_probability=float(item.no_vig_probability),
            edge=float(item.edge),
            ev=float(item.ev),
            opportunity_score=float(item.opportunity_score),
            rank=rank,
            odds_source=item.odds_source,
            model_version=item.model_version,
            model_status=item.model_status,
            value_engine_version=item.value_engine_version,
            ai_picks_version=AI_PICKS_VERSION,
            cutoff_at=item.cutoff_at,
            generated_at=item.generated_at,
            data_mode=item.data_mode,
        )
