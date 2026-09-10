from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.predictions.exceptions import ArtefactNotFoundError
from app.predictions.runtime import ensure_ml_on_path
from app.predictions.simplex import renormalize_1x2
from app.predictions.types import (
    CANDIDATE_MODEL_VERSION,
    CANDIDATE_STATUS,
    Football1x2Model,
    ModelStatus,
    OutcomeProbabilities,
    PitEloFeatures,
)


class CandidateEloAdapter:
    """Loads football-elo-v1-candidate. A later champion implements Football1x2Model instead."""

    def __init__(
        self,
        *,
        artefact: dict[str, Any],
        card: dict[str, Any] | None,
        artefact_path: Path,
    ) -> None:
        status = str(artefact.get("status") or (card or {}).get("status") or "")
        if status != CANDIDATE_STATUS:
            raise ArtefactNotFoundError(
                f"Refusing artefact at {artefact_path}: status must be '{CANDIDATE_STATUS}', not production."
            )
        selected = str(artefact.get("selected") or "")
        if selected != "elo":
            raise ArtefactNotFoundError(f"Refusing artefact at {artefact_path}: selected model is not elo.")
        predictors = artefact.get("predictors")
        if not isinstance(predictors, dict) or "elo" not in predictors:
            raise ArtefactNotFoundError("Candidate artefact is missing the elo predictor.")
        self._predictor = predictors["elo"]
        calibrators = artefact.get("calibrators")
        self._calibrator = calibrators.get("elo") if isinstance(calibrators, dict) else None
        version = str((card or {}).get("model_version") or CANDIDATE_MODEL_VERSION)
        if version != CANDIDATE_MODEL_VERSION:
            raise ArtefactNotFoundError(
                f"Refusing artefact version '{version}'; this service serves {CANDIDATE_MODEL_VERSION} only."
            )
        self._model_version = version
        self._dataset_version = str((card or {}).get("dataset_version") or artefact.get("dataset_version") or "")
        self._feature_schema_version = str((card or {}).get("feature_schema_version") or "")
        if not self._dataset_version or not self._feature_schema_version:
            raise ArtefactNotFoundError("Candidate artefact card is missing dataset or feature schema versions.")

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def model_status(self) -> ModelStatus:
        return CANDIDATE_STATUS

    @property
    def dataset_version(self) -> str:
        return self._dataset_version

    @property
    def feature_schema_version(self) -> str:
        return self._feature_schema_version

    def predict_1x2(self, features: PitEloFeatures) -> OutcomeProbabilities:
        ensure_ml_on_path()
        import numpy as np

        diffs = np.array([features.elo_diff], dtype=np.float64)
        raw = np.asarray(self._predictor.predict_diffs(diffs), dtype=np.float64)
        if raw.shape != (1, 3):
            raise ArtefactNotFoundError("Candidate elo predictor did not return a 1x3 probability vector.")
        calibrated = raw
        if self._calibrator is not None:
            calibrated = np.asarray(self._calibrator.transform(raw), dtype=np.float64)
        row = calibrated[0]
        return renormalize_1x2(float(row[0]), float(row[1]), float(row[2]))


def load_football_1x2_model(*, registry_dir: Path, model_version: str) -> Football1x2Model:
    """Registry entry point. Future champions register here without changing HTTP."""

    if model_version != CANDIDATE_MODEL_VERSION:
        raise ArtefactNotFoundError(
            f"Model '{model_version}' is not served. V1 loads {CANDIDATE_MODEL_VERSION} as candidate only."
        )
    directory = registry_dir.expanduser().resolve() / model_version
    artefact_path = directory / "artefact.joblib"
    if not artefact_path.is_file():
        raise ArtefactNotFoundError(f"Registry artefact not found: {artefact_path}")
    ensure_ml_on_path()
    from predicta_ml.registry.artifact import load_registry

    artefact = load_registry(artefact_path)
    card_path = directory / "registry.json"
    card: dict[str, Any] | None = None
    if card_path.is_file():
        loaded = json.loads(card_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ArtefactNotFoundError("Registry card is not a JSON object.")
        card = loaded
    return CandidateEloAdapter(artefact=artefact, card=card, artefact_path=artefact_path)
