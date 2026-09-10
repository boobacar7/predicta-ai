from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.clock import Clock
from app.predictions.exceptions import ArtefactNotFoundError, PitFeaturesUnavailableError
from app.predictions.features import ParquetPitFeatureStore, PitFeatureStore
from app.predictions.models import load_football_1x2_model
from app.predictions.types import MARKET_1X2, SPORT_FOOTBALL, Football1x2Model
from app.schemas import FootballModelPrediction


class FootballPredictionService:
    def __init__(
        self,
        *,
        clock: Clock,
        features: PitFeatureStore,
        model: Football1x2Model,
    ) -> None:
        self._clock = clock
        self._features = features
        self._model = model

    def predict(self, match_id: str, cutoff_at: datetime | None) -> FootballModelPrediction:
        snapshot = self._features.get_pit_features(match_id, cutoff_at)
        if snapshot.dataset_version != self._model.dataset_version:
            raise PitFeaturesUnavailableError("Feature dataset_version does not match the loaded candidate artefact.")
        if snapshot.feature_schema_version != self._model.feature_schema_version:
            raise PitFeaturesUnavailableError(
                "Feature schema version does not match the loaded candidate artefact."
            )
        probabilities = self._model.predict_1x2(snapshot)
        generated_at = self._clock.now()
        return FootballModelPrediction(
            match_id=snapshot.match_id,
            sport=SPORT_FOOTBALL,
            market=MARKET_1X2,
            home_probability=probabilities.home,
            draw_probability=probabilities.draw,
            away_probability=probabilities.away,
            model_version=self._model.model_version,
            dataset_version=self._model.dataset_version,
            feature_schema_version=self._model.feature_schema_version,
            model_status=self._model.model_status,
            cutoff_at=snapshot.cutoff_at,
            cutoff_policy=snapshot.cutoff_policy,
            generated_at=generated_at,
        )


def build_football_prediction_service(
    *,
    clock: Clock,
    registry_dir: Path,
    dataset_path: Path,
    model_version: str,
) -> FootballPredictionService:
    if not dataset_path.expanduser().resolve().is_file():
        raise PitFeaturesUnavailableError(f"PIT dataset parquet was not found: {dataset_path}")
    if not (registry_dir.expanduser().resolve() / model_version / "artefact.joblib").is_file():
        raise ArtefactNotFoundError(
            f"Registry artefact not found: {registry_dir / model_version / 'artefact.joblib'}"
        )
    return FootballPredictionService(
        clock=clock,
        features=ParquetPitFeatureStore(dataset_path),
        model=load_football_1x2_model(registry_dir=registry_dir, model_version=model_version),
    )
