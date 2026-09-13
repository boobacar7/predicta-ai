from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from predicta_ml.constants import (
    CANDIDATE_MODEL_VERSION,
    CANDIDATE_STATUS,
    DATASET_VERSION,
    FEATURE_SCHEMA_VERSION,
    default_committed_reports_dir,
    default_output_dir,
)
from predicta_ml.oos.errors import OosProtocolError
from predicta_ml.oos.protocol import (
    CALIBRATION_CUTOFF,
    CANDIDATE_CODE_VERSION,
    CANDIDATE_CREATED_AT,
    CANDIDATE_DATASET_SHA256,
    OOS_START,
    REJECTED_PERIODS,
    TRAIN_CUTOFF,
    classify_event_at,
    is_true_oos_event,
)


def committed_registry_path() -> Path:
    return default_committed_reports_dir() / f"{CANDIDATE_MODEL_VERSION}.registry.json"


def committed_summary_path() -> Path:
    return default_committed_reports_dir() / f"{CANDIDATE_MODEL_VERSION}.summary.json"


def local_registry_card_path() -> Path:
    return default_output_dir() / "registry" / CANDIDATE_MODEL_VERSION / "registry.json"


def local_artefact_path() -> Path:
    return default_output_dir() / "registry" / CANDIDATE_MODEL_VERSION / "artefact.joblib"


@dataclass(frozen=True)
class ModelProvenance:
    model_version: str
    status: str
    promoted_to_production: bool
    dataset_version: str
    dataset_sha256: str
    feature_schema_version: str
    calibration_method: str
    code_version: str
    created_at: datetime | None
    train_start: datetime
    train_end_exclusive: datetime
    train_rows: int
    latest_training_event_at_exclusive: datetime
    calibration_fit_start: datetime
    calibration_fit_end_exclusive: datetime
    calibration_fit_rows: int
    calibration_select_start: datetime
    calibration_select_end_exclusive: datetime
    calibration_select_rows: int
    latest_calibration_event_at_exclusive: datetime
    test_start: datetime
    test_end_exclusive: datetime
    test_rows: int
    freeze_at: datetime
    earliest_legitimate_oos: datetime
    selected_model: str
    hyperparameters: dict[str, Any]
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "status": self.status,
            "promoted_to_production": self.promoted_to_production,
            "dataset_version": self.dataset_version,
            "dataset_sha256": self.dataset_sha256,
            "feature_schema_version": self.feature_schema_version,
            "calibration_method": self.calibration_method,
            "code_version": self.code_version,
            "created_at": _iso(self.created_at) if self.created_at is not None else None,
            "training": {
                "start": self.train_start.isoformat(),
                "end_exclusive": self.train_end_exclusive.isoformat(),
                "rows": self.train_rows,
                "latest_event_at_exclusive": self.latest_training_event_at_exclusive.isoformat(),
                "latest_available_at_note": (
                    "available_at is not a parquet column. Data-layer Elo updates use "
                    "event_at + 3h; training labels satisfy event_at < train_end_exclusive."
                ),
            },
            "calibration": {
                "method": self.calibration_method,
                "fit": {
                    "start": self.calibration_fit_start.isoformat(),
                    "end_exclusive": self.calibration_fit_end_exclusive.isoformat(),
                    "rows": self.calibration_fit_rows,
                },
                "select": {
                    "start": self.calibration_select_start.isoformat(),
                    "end_exclusive": self.calibration_select_end_exclusive.isoformat(),
                    "rows": self.calibration_select_rows,
                },
                "latest_event_at_exclusive": self.latest_calibration_event_at_exclusive.isoformat(),
            },
            "test": {
                "start": self.test_start.isoformat(),
                "end_exclusive": self.test_end_exclusive.isoformat(),
                "rows": self.test_rows,
            },
            "freeze": {
                "artefact_created_at": _iso(self.created_at) if self.created_at is not None else None,
                "temporal_freeze_at": self.freeze_at.isoformat(),
                "earliest_legitimate_oos": self.earliest_legitimate_oos.isoformat(),
                "note": (
                    "The artefact is temporally frozen at calibration_select end_exclusive. "
                    "Matches with event_at >= that instant are the only legitimate OOS sample "
                    "for this frozen candidate, including its sigmoid calibrator."
                ),
            },
            "selected_model": self.selected_model,
            "hyperparameters": self.hyperparameters,
            "source_path": self.source_path,
        }


def load_registry_card(path: Path | None = None) -> dict[str, Any]:
    resolved = (path or committed_registry_path()).expanduser().resolve()
    if not resolved.is_file():
        raise OosProtocolError(f"Candidate registry card not found: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise OosProtocolError("Candidate registry card is not a JSON object.")
    return payload


def load_summary_card(path: Path | None = None) -> dict[str, Any]:
    resolved = (path or committed_summary_path()).expanduser().resolve()
    if not resolved.is_file():
        raise OosProtocolError(f"Candidate summary not found: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise OosProtocolError("Candidate summary is not a JSON object.")
    return payload


def audit_model_provenance(
    *,
    registry_path: Path | None = None,
    summary_path: Path | None = None,
) -> ModelProvenance:
    card = load_registry_card(registry_path)
    summary = load_summary_card(summary_path)
    _assert_candidate(card, summary)
    training = _period(card["training_period"], expected_end=TRAIN_CUTOFF, name="training_period")
    calibration = card["validation_period"]
    fit = _period(calibration["calibration_fit"], expected_end=None, name="calibration_fit")
    select = _period(calibration["calibration_select"], expected_end=CALIBRATION_CUTOFF, name="calibration_select")
    test = _period(card["test_period"], expected_start=OOS_START, name="test_period")
    created_at = _parse_optional_datetime(card.get("created_at"))
    if created_at is None:
        created_at = CANDIDATE_CREATED_AT
    freeze_at = select["end_exclusive"]
    if freeze_at != CALIBRATION_CUTOFF or freeze_at != OOS_START:
        raise OosProtocolError("Calibration select end is not the documented OOS start.")
    hyperparameters = dict(card["hyperparameters"])
    return ModelProvenance(
        model_version=str(card["model_version"]),
        status=str(card["status"]),
        promoted_to_production=bool(summary["promoted_to_production"]),
        dataset_version=str(card["dataset_version"]),
        dataset_sha256=str(card["dataset_sha256"]),
        feature_schema_version=str(card["feature_schema_version"]),
        calibration_method=str(card["calibration_method"]),
        code_version=str(card["code_version"]),
        created_at=created_at,
        train_start=training["start"],
        train_end_exclusive=training["end_exclusive"],
        train_rows=training["rows"],
        latest_training_event_at_exclusive=training["end_exclusive"],
        calibration_fit_start=fit["start"],
        calibration_fit_end_exclusive=fit["end_exclusive"],
        calibration_fit_rows=fit["rows"],
        calibration_select_start=select["start"],
        calibration_select_end_exclusive=select["end_exclusive"],
        calibration_select_rows=select["rows"],
        latest_calibration_event_at_exclusive=select["end_exclusive"],
        test_start=test["start"],
        test_end_exclusive=test["end_exclusive"],
        test_rows=test["rows"],
        freeze_at=freeze_at,
        earliest_legitimate_oos=OOS_START,
        selected_model=str(card["selected_model"]),
        hyperparameters=hyperparameters,
        source_path=str((registry_path or committed_registry_path()).expanduser().resolve()),
    )


def assert_window_is_oos(
    *,
    start: datetime,
    end_exclusive: datetime,
    provenance: ModelProvenance,
) -> None:
    window_start = start.astimezone(UTC)
    window_end = end_exclusive.astimezone(UTC)
    if window_end <= window_start:
        raise OosProtocolError("OOS window end must be after start.")
    if window_start < provenance.earliest_legitimate_oos:
        raise OosProtocolError(
            f"Proposed OOS start {window_start.isoformat()} is before the artefact freeze "
            f"{provenance.earliest_legitimate_oos.isoformat()}. Running the frozen candidate "
            "on earlier matches is not a true OOS evaluation."
        )
    if window_start < provenance.latest_calibration_event_at_exclusive:
        raise OosProtocolError("Proposed OOS window overlaps calibration.")
    if window_start < provenance.latest_training_event_at_exclusive:
        raise OosProtocolError("Proposed OOS window overlaps training.")


def reject_period_if_invalid(event_at: datetime, provenance: ModelProvenance) -> str | None:
    if is_true_oos_event(event_at) and event_at.astimezone(UTC) >= provenance.earliest_legitimate_oos:
        return None
    split = classify_event_at(event_at)
    for period in REJECTED_PERIODS:
        if period.start <= event_at.astimezone(UTC) < period.end_exclusive:
            return period.reason
    return f"event_at {event_at.isoformat()} is not after artefact freeze ({split})."


def provenance_summary(provenance: ModelProvenance) -> dict[str, Any]:
    return {
        "kind": "football-elo-v1-candidate-provenance",
        "model": provenance.to_dict(),
        "earliest_legitimate_oos": provenance.earliest_legitimate_oos.isoformat(),
        "rejected_periods": [
            {
                "name": item.name,
                "start": item.start.isoformat(),
                "end_exclusive": item.end_exclusive.isoformat(),
                "temporal_split": item.temporal_split,
                "reason": item.reason,
            }
            for item in REJECTED_PERIODS
        ],
        "constants_checked": {
            "dataset_version": DATASET_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "expected_dataset_sha256": CANDIDATE_DATASET_SHA256,
            "expected_code_version": CANDIDATE_CODE_VERSION,
        },
    }


def _assert_candidate(card: dict[str, Any], summary: dict[str, Any]) -> None:
    if card.get("model_version") != CANDIDATE_MODEL_VERSION:
        raise OosProtocolError(f"Registry model_version is {card.get('model_version')!r}, not the frozen candidate.")
    if card.get("status") != CANDIDATE_STATUS:
        raise OosProtocolError("Refusing a non-candidate artefact for the OOS protocol.")
    if summary.get("promoted_to_production") is True:
        raise OosProtocolError("Candidate has been promoted; this task must not treat it as production.")
    if card.get("dataset_version") != DATASET_VERSION:
        raise OosProtocolError("Registry dataset_version does not match football-1x2-history-0.3.")
    if card.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise OosProtocolError("Registry feature schema does not match football-1x2-features-0.3.")
    if card.get("dataset_sha256") != CANDIDATE_DATASET_SHA256:
        raise OosProtocolError("Registry dataset SHA-256 does not match the frozen candidate card.")
    if card.get("calibration_method") != "sigmoid":
        raise OosProtocolError("Frozen candidate calibration_method must be sigmoid.")
    if card.get("selected_model") != "elo":
        raise OosProtocolError("Frozen candidate selected_model must be elo.")


def _period(
    payload: dict[str, Any],
    *,
    name: str,
    expected_end: datetime | None = None,
    expected_start: datetime | None = None,
) -> dict[str, Any]:
    start = _parse_datetime(payload.get("start"), field=f"{name}.start")
    end = _parse_datetime(payload.get("end_exclusive"), field=f"{name}.end_exclusive")
    if expected_end is not None and end != expected_end:
        raise OosProtocolError(f"{name}.end_exclusive is {end.isoformat()}, expected {expected_end.isoformat()}.")
    if expected_start is not None and start != expected_start:
        raise OosProtocolError(f"{name}.start is {start.isoformat()}, expected {expected_start.isoformat()}.")
    rows = payload.get("rows")
    if not isinstance(rows, int) or rows <= 0:
        raise OosProtocolError(f"{name}.rows is missing or not a positive integer.")
    return {"start": start, "end_exclusive": end, "rows": rows}


def _parse_datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise OosProtocolError(f"{field} is missing from the registry card.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise OosProtocolError(f"{field} must be timezone-aware UTC.")
    return parsed.astimezone(UTC)


def _parse_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise OosProtocolError("created_at must be timezone-aware UTC.")
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()
