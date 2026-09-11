from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from predicta_ml.constants import CANDIDATE_MODEL_VERSION, ELO_HOME_ADVANTAGE, ELO_K, ELO_SCALE, FEATURE_SCHEMA_VERSION
from predicta_ml.models.elo import EloBaseline, elo_1x2_probabilities
from predicta_ml.oos.dataset import OosMatch
from predicta_ml.oos.errors import OosLeakageError, OosProtocolError
from predicta_ml.oos.provenance import ModelProvenance, local_artefact_path
from predicta_ml.registry.artifact import load_registry


@dataclass(frozen=True)
class FrozenPrediction:
    match_id: str
    home: float
    draw: float
    away: float
    model_version: str
    calibration_method: str
    used_artefact: bool

    def as_array(self) -> np.ndarray:
        return np.array([self.home, self.draw, self.away], dtype=np.float64)

    def to_dict(self) -> dict[str, object]:
        return {
            "match_id": self.match_id,
            "home_probability": self.home,
            "draw_probability": self.draw,
            "away_probability": self.away,
            "model_version": self.model_version,
            "calibration_method": self.calibration_method,
            "used_artefact": self.used_artefact,
        }


@dataclass(frozen=True)
class FrozenEloPredictor:
    """Frozen candidate parameters. Does not refit K, HA, draw, or calibration."""

    draw_base: float
    draw_decay: float
    home_advantage: float
    scale: float
    k: float
    calibration_method: str
    calibrator: Any | None
    used_artefact: bool
    model_version: str = CANDIDATE_MODEL_VERSION
    feature_schema_version: str = FEATURE_SCHEMA_VERSION

    def predict_match(self, match: OosMatch) -> FrozenPrediction:
        raw = elo_1x2_probabilities(
            np.array([match.elo_diff], dtype=np.float64),
            home_advantage=self.home_advantage,
            scale=self.scale,
            draw_base=self.draw_base,
            draw_decay=self.draw_decay,
        )
        calibrated = raw
        if self.calibrator is not None:
            calibrated = np.asarray(self.calibrator.transform(raw), dtype=np.float64)
        row = calibrated[0]
        total = float(row.sum())
        if not np.isfinite(total) or abs(total - 1.0) > 1e-8:
            raise OosProtocolError(f"Frozen prediction for {match.match_id} is not a simplex.")
        return FrozenPrediction(
            match_id=match.match_id,
            home=float(row[0]),
            draw=float(row[1]),
            away=float(row[2]),
            model_version=self.model_version,
            calibration_method=self.calibration_method,
            used_artefact=self.used_artefact,
        )

    def predict_many(self, matches: tuple[OosMatch, ...]) -> tuple[FrozenPrediction, ...]:
        return tuple(self.predict_match(item) for item in matches)


def frozen_predictor_from_provenance(
    provenance: ModelProvenance,
    *,
    artefact_path: Path | None = None,
) -> FrozenEloPredictor:
    params = provenance.hyperparameters
    draw_base = float(params["draw_base"])
    draw_decay = float(params["draw_decay"])
    home_advantage = float(params.get("home_advantage", ELO_HOME_ADVANTAGE))
    scale = float(params.get("scale", ELO_SCALE))
    k = float(params.get("k", ELO_K))
    if k != ELO_K or home_advantage != ELO_HOME_ADVANTAGE:
        raise OosProtocolError("Refusing to alter frozen Elo K / home advantage.")
    path = artefact_path if artefact_path is not None else local_artefact_path()
    calibrator = None
    used_artefact = False
    if path.expanduser().resolve().is_file():
        artefact = load_registry(path)
        _assert_artefact_is_candidate(artefact, provenance)
        predictor = artefact["predictors"]["elo"]
        if not isinstance(predictor, EloBaseline):
            raise OosProtocolError("Candidate artefact elo predictor is not EloBaseline.")
        if abs(float(predictor.draw_base_) - draw_base) > 1e-12:
            raise OosProtocolError("Artefact draw_base does not match the frozen registry card.")
        if abs(float(predictor.draw_decay_) - draw_decay) > 1e-12:
            raise OosProtocolError("Artefact draw_decay does not match the frozen registry card.")
        calibrators = artefact.get("calibrators")
        if isinstance(calibrators, dict):
            calibrator = calibrators.get("elo")
        used_artefact = True
    method = provenance.calibration_method if calibrator is not None else "raw"
    return FrozenEloPredictor(
        draw_base=draw_base,
        draw_decay=draw_decay,
        home_advantage=home_advantage,
        scale=scale,
        k=k,
        calibration_method=method,
        calibrator=calibrator,
        used_artefact=used_artefact,
    )


def probability_matrix(predictions: tuple[FrozenPrediction, ...]) -> np.ndarray:
    if not predictions:
        return np.zeros((0, 3), dtype=np.float64)
    return np.vstack([item.as_array() for item in predictions])


def _assert_artefact_is_candidate(artefact: dict[str, Any], provenance: ModelProvenance) -> None:
    if artefact.get("status") != "candidate":
        raise OosLeakageError("Refusing a non-candidate joblib artefact.")
    if artefact.get("selected") != "elo":
        raise OosProtocolError("Artefact selected model is not elo.")
    parameters = artefact.get("parameters")
    if isinstance(parameters, dict):
        method = parameters.get("calibration_method")
        if method not in {None, provenance.calibration_method}:
            raise OosProtocolError("Artefact calibration_method does not match the registry card.")
