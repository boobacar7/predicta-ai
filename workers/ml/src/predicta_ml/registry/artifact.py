from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
from pydantic import BaseModel, ConfigDict, Field

from predicta_ml.constants import (
    DATASET_VERSION,
    FEATURE_SCHEMA_VERSION,
    MARKET,
    MODEL_VERSION,
    PACKAGE_VERSION,
    RANDOM_SEED,
    SPORT,
)
from predicta_ml.errors import RegistryError
from predicta_ml.features.schema import BOOSTING_FEATURES


class RegistryCard(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_version: str
    dataset_version: str
    feature_schema_version: str
    market: str = MARKET
    sport: str = SPORT
    training_period: dict[str, Any]
    validation_period: dict[str, Any]
    test_period: dict[str, Any]
    features: list[str]
    hyperparameters: dict[str, Any]
    metrics: dict[str, Any]
    calibration_method: str
    random_seed: int
    code_version: str
    dataset_sha256: str
    selected_model: str
    ensemble_used: bool
    status: str = "not_production"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: list[str]


def write_registry(
    output_dir: Path,
    *,
    card: RegistryCard,
    artefact: dict[str, Any],
) -> dict[str, str]:
    directory = output_dir / card.model_version
    directory.mkdir(parents=True, exist_ok=True)
    card_path = directory / "registry.json"
    artefact_path = directory / "artefact.joblib"
    try:
        card_path.write_text(json.dumps(card.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
        joblib.dump(artefact, artefact_path)
    except OSError as exc:
        raise RegistryError(f"Failed to write registry: {exc}") from exc
    return {"card": str(card_path), "artefact": str(artefact_path)}


def load_registry(artefact_path: Path) -> dict[str, Any]:
    path = artefact_path.expanduser().resolve()
    if not path.is_file():
        raise RegistryError(f"Registry artefact not found: {path}")
    payload = joblib.load(path)
    if not isinstance(payload, dict):
        raise RegistryError("Registry artefact is not a mapping.")
    return payload


def default_card_kwargs() -> dict[str, Any]:
    return {
        "model_version": MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": list(BOOSTING_FEATURES),
        "random_seed": RANDOM_SEED,
        "code_version": PACKAGE_VERSION,
    }
