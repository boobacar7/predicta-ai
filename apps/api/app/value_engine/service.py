from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.core.clock import Clock
from app.odds.service import OddsService
from app.odds.types import FOOTBALL_1X2_MARKET, Football1x2Selection
from app.predictions.types import SPORT_FOOTBALL
from app.schemas import FootballModelPrediction
from app.value_engine import calculator
from app.value_engine.exceptions import InvalidPredictionError
from app.value_engine.models import (
    FootballValueAnalysis,
    SelectionMarketProbabilities,
    SelectionValue,
    ValueBySelection,
    ValueMarket,
    ValueMetadata,
    ValueOdds,
    ValuePrediction,
)

_REQUIRED_PREDICTION_METADATA = (
    "model_version",
    "model_status",
    "dataset_version",
    "feature_schema_version",
    "cutoff_at",
    "cutoff_policy",
    "generated_at",
)


class PredictionService(Protocol):
    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction: ...


class FootballValueService:
    def __init__(
        self,
        *,
        clock: Clock,
        predictions: PredictionService,
        odds: OddsService,
    ) -> None:
        self._clock = clock
        self._predictions = predictions
        self._odds = odds

    def evaluate(self, match_id: str, cutoff_at: datetime | None) -> FootballValueAnalysis:
        prediction = self._predictions.predict(match_id, cutoff_at)
        model_probabilities = self._validate_prediction(prediction, match_id, cutoff_at)
        odds_cutoff = cutoff_at if cutoff_at is not None else prediction.cutoff_at
        snapshot = self._odds.market_at(
            match_id=match_id,
            market=FOOTBALL_1X2_MARKET,
            cutoff_at=odds_cutoff,
        )
        odds_by_selection = {
            item.selection: item.decimal_odds
            for item in snapshot.selections
        }
        no_vig, overround = calculator.no_vig_probabilities(odds_by_selection)
        implied = {
            selection: calculator.implied_probability(odds)
            for selection, odds in odds_by_selection.items()
        }
        values = {
            selection: SelectionValue(
                edge=float(calculator.edge(model_probabilities[selection], implied[selection])),
                ev=float(calculator.expected_value(model_probabilities[selection], odds_by_selection[selection])),
            )
            for selection in Football1x2Selection
        }
        markets = {
            selection: SelectionMarketProbabilities(
                implied_probability=float(implied[selection]),
                no_vig_probability=float(no_vig[selection]),
            )
            for selection in Football1x2Selection
        }
        generated_at = self._clock.now()
        return FootballValueAnalysis(
            match_id=match_id,
            prediction=ValuePrediction(
                home_probability=float(model_probabilities[Football1x2Selection.HOME]),
                draw_probability=float(model_probabilities[Football1x2Selection.DRAW]),
                away_probability=float(model_probabilities[Football1x2Selection.AWAY]),
            ),
            odds=ValueOdds(
                bookmaker=snapshot.bookmaker,
                provider_id=snapshot.provider_id,
                home_odds=float(odds_by_selection[Football1x2Selection.HOME]),
                draw_odds=float(odds_by_selection[Football1x2Selection.DRAW]),
                away_odds=float(odds_by_selection[Football1x2Selection.AWAY]),
                collected_at=snapshot.collected_at,
                available_at=snapshot.available_at,
            ),
            market_probabilities=ValueMarket(
                overround=float(overround),
                home=markets[Football1x2Selection.HOME],
                draw=markets[Football1x2Selection.DRAW],
                away=markets[Football1x2Selection.AWAY],
            ),
            value=ValueBySelection(
                home=values[Football1x2Selection.HOME],
                draw=values[Football1x2Selection.DRAW],
                away=values[Football1x2Selection.AWAY],
            ),
            metadata=ValueMetadata(
                value_engine_version=calculator.VALUE_ENGINE_VERSION,
                model_version=prediction.model_version,
                model_status=prediction.model_status,
                dataset_version=prediction.dataset_version,
                feature_schema_version=prediction.feature_schema_version,
                odds_source=snapshot.source,
                cutoff_at=prediction.cutoff_at,
                generated_at=generated_at,
                data_mode=snapshot.data_mode,
            ),
        )

    @staticmethod
    def _validate_prediction(
        prediction: FootballModelPrediction,
        match_id: str,
        requested_cutoff: datetime | None,
    ) -> dict[Football1x2Selection, Decimal]:
        try:
            if prediction.match_id != match_id:
                raise InvalidPredictionError("Prediction match_id does not match the requested match.")
            if prediction.sport != SPORT_FOOTBALL or prediction.market != FOOTBALL_1X2_MARKET:
                raise InvalidPredictionError("Prediction is incompatible with football 1X2 value.")
            FootballValueService._require_metadata(prediction)
            if requested_cutoff is not None and prediction.cutoff_at > requested_cutoff:
                raise InvalidPredictionError(
                    "Prediction cutoff_at is after the requested cutoff_at."
                )
            try:
                probabilities = {
                    Football1x2Selection.HOME: calculator.probability(prediction.home_probability),
                    Football1x2Selection.DRAW: calculator.probability(prediction.draw_probability),
                    Football1x2Selection.AWAY: calculator.probability(prediction.away_probability),
                }
            except (AttributeError, TypeError, ValueError) as exc:
                raise InvalidPredictionError(str(exc) or "Prediction probabilities are invalid.") from exc
        except AttributeError as exc:
            raise InvalidPredictionError("Prediction is missing required metadata.") from exc
        if abs(sum(probabilities.values(), Decimal(0)) - Decimal(1)) > Decimal("0.000000001"):
            raise InvalidPredictionError("Prediction probabilities must sum to 1.")
        return probabilities

    @staticmethod
    def _require_metadata(prediction: FootballModelPrediction) -> None:
        try:
            values = {name: getattr(prediction, name) for name in _REQUIRED_PREDICTION_METADATA}
        except AttributeError as exc:
            raise InvalidPredictionError("Prediction is missing required metadata.") from exc
        for name, value in values.items():
            if value is None or value == "":
                raise InvalidPredictionError(f"Prediction is missing required metadata: {name}.")
