from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.ai_analyst.context import (
    AnalystContext,
    AnalystIdentity,
    AnalystPrediction,
    highest_ev_selection,
    value_for_selection,
)
from app.ai_analyst.deterministic import DeterministicAnalystProvider
from app.ai_analyst.grounding import assert_grounded
from app.ai_analyst.models import FootballAiAnalystReport
from app.ai_analyst.provider import AnalystProvider
from app.core.clock import Clock
from app.core.errors import NotFoundError
from app.match_identity.models import MatchIdentity
from app.odds.exceptions import IncompleteOddsMarketError, OddsTemporalLeakageError, OddsUnavailableError
from app.odds.types import DataMode
from app.predictions.exceptions import TemporalLeakageError
from app.schemas import FootballModelPrediction
from app.value_engine.exceptions import InvalidPredictionError
from app.value_engine.models import FootballValueAnalysis


class PredictionService(Protocol):
    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction: ...


class ValueService(Protocol):
    def evaluate(self, match_id: str, cutoff_at: datetime | None) -> FootballValueAnalysis: ...


class IdentityRepository(Protocol):
    def get(self, match_id: str) -> MatchIdentity | None: ...


class FootballAnalystService:
    """Assemble a PIT-safe context, then ask the provider to explain it."""

    def __init__(
        self,
        *,
        clock: Clock,
        identities: IdentityRepository,
        predictions: PredictionService,
        values: ValueService,
        provider: AnalystProvider | None = None,
    ) -> None:
        self._clock = clock
        self._identities = identities
        self._predictions = predictions
        self._values = values
        self._provider = provider or DeterministicAnalystProvider()

    def explain(self, match_id: str, cutoff_at: datetime | None) -> FootballAiAnalystReport:
        identity = self._identities.get(match_id)
        if identity is None:
            raise NotFoundError("Match not found.", instance=f"/football/ai-analyst/{match_id}")
        prediction = self._predictions.predict(match_id, cutoff_at)
        self._validate_prediction_cutoff(identity, prediction, cutoff_at)
        analyst_prediction = AnalystPrediction(
            home_probability=Decimal(str(prediction.home_probability)),
            draw_probability=Decimal(str(prediction.draw_probability)),
            away_probability=Decimal(str(prediction.away_probability)),
            model_version=prediction.model_version,
            model_status=prediction.model_status,
            dataset_version=prediction.dataset_version,
            cutoff_at=prediction.cutoff_at,
        )
        context_identity = AnalystIdentity(
            match_id=identity.match_id,
            home_team=identity.home_team,
            away_team=identity.away_team,
            league=identity.league,
            kickoff_at=identity.kickoff_at,
        )
        value_analysis = self._optional_value(match_id, prediction.cutoff_at)
        value = None
        best_ev = None
        if value_analysis is not None:
            self._validate_value_cutoff(identity, prediction, value_analysis)
            value = value_for_selection(value_analysis, analyst_prediction.favorite_selection())
            best_ev = highest_ev_selection(value_analysis)
        context = AnalystContext(
            identity=context_identity,
            prediction=analyst_prediction,
            value=value,
            generated_at=self._clock.now(),
            data_mode=self._resolved_data_mode(identity, value_analysis),
            value_selection=best_ev,
        )
        explanation = self._provider.generate_analysis(context)
        assert_grounded(context, explanation)
        return FootballAiAnalystReport(
            match_id=identity.match_id,
            home_team=identity.home_team,
            away_team=identity.away_team,
            league=identity.league,
            kickoff_at=identity.kickoff_at,
            model_favorite=context.favorite_selection().value,
            prediction=context.to_prediction_dto(),
            value=context.to_value_dto(),
            analyst=explanation,
        )

    def _optional_value(self, match_id: str, cutoff_at: datetime) -> FootballValueAnalysis | None:
        try:
            return self._values.evaluate(match_id, cutoff_at)
        except (OddsUnavailableError, IncompleteOddsMarketError):
            return None

    @staticmethod
    def _resolved_data_mode(identity: MatchIdentity, analysis: FootballValueAnalysis | None) -> DataMode:
        if identity.data_mode == "live" and analysis is not None and analysis.metadata.data_mode == "live":
            return "live"
        return "mock"

    @staticmethod
    def _validate_prediction_cutoff(
        identity: MatchIdentity,
        prediction: FootballModelPrediction,
        requested_cutoff: datetime | None,
    ) -> None:
        if prediction.match_id != identity.match_id:
            raise InvalidPredictionError("Prediction match_id does not match the requested match.")
        if requested_cutoff is not None and prediction.cutoff_at > requested_cutoff:
            raise TemporalLeakageError("Prediction cutoff_at is after the requested cutoff_at.")
        if identity.kickoff_at != prediction.cutoff_at:
            raise TemporalLeakageError("Analyst cutoff does not match the match kickoff PIT boundary.")

    @staticmethod
    def _validate_value_cutoff(
        identity: MatchIdentity,
        prediction: FootballModelPrediction,
        analysis: FootballValueAnalysis,
    ) -> None:
        if analysis.match_id != identity.match_id:
            raise InvalidPredictionError("Value analysis identity is inconsistent with the match.")
        if analysis.odds.available_at > prediction.cutoff_at:
            raise OddsTemporalLeakageError("Odds available_at is after the canonical prediction cutoff.")
        if analysis.odds.available_at > identity.kickoff_at:
            raise OddsTemporalLeakageError("Odds available_at is after match kickoff.")
        if analysis.metadata.cutoff_at > prediction.cutoff_at:
            raise TemporalLeakageError("Value analysis cutoff is after the prediction cutoff.")
