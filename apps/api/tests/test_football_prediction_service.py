from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.core.clock import Clock
from app.predictions.exceptions import ArtefactNotFoundError, PitFeaturesUnavailableError, TemporalLeakageError
from app.predictions.features import InMemoryPitFeatureStore, ParquetPitFeatureStore
from app.predictions.models import load_football_1x2_model
from app.predictions.service import FootballPredictionService
from app.predictions.simplex import renormalize_1x2
from app.predictions.types import (
    CANDIDATE_MODEL_VERSION,
    CANDIDATE_STATUS,
    CUTOFF_POLICY_PRE_KICKOFF,
    ELO_FEATURES,
    PitEloFeatures,
)

REPO = Path(__file__).resolve().parents[3]
ARTEFACT_DIR = REPO / "workers" / "ml" / "var" / "registry"
DATASET = REPO / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
LIVE_MATCH_ID = "mth_football-sportmonks-19719892"
LIVE_KICKOFF = datetime(2026, 7, 7, 16, 0, tzinfo=UTC)


def _require_live_assets() -> None:
    if not (ARTEFACT_DIR / CANDIDATE_MODEL_VERSION / "artefact.joblib").is_file():
        pytest.fail("football-elo-v1-candidate artefact.joblib is required; the real model must not be mocked.")
    if not DATASET.is_file():
        pytest.fail("football-1x2-history-0.3 parquet is required for PIT features.")


def _snapshot(
    match_id: str = "mth_unit",
    *,
    event_at: datetime = LIVE_KICKOFF,
    home: float = 1500.0,
    away: float = 1480.0,
    data_mode: str = "live",
) -> PitEloFeatures:
    return PitEloFeatures(
        match_id=match_id,
        event_at=event_at,
        cutoff_at=event_at,
        cutoff_policy=CUTOFF_POLICY_PRE_KICKOFF,
        dataset_version="football-1x2-history-0.3",
        feature_schema_version="football-1x2-features-0.3",
        data_mode=data_mode,
        home_elo_pre=home,
        away_elo_pre=away,
        elo_diff=home - away,
    )


def test_renormalized_probabilities_sum_to_one() -> None:
    result = renormalize_1x2(0.2, 0.3, 0.5)
    assert result.total() == pytest.approx(1.0, abs=1e-12)


def test_artefact_not_found(tmp_path: Path) -> None:
    with pytest.raises(ArtefactNotFoundError) as exc:
        load_football_1x2_model(registry_dir=tmp_path, model_version=CANDIDATE_MODEL_VERSION)
    assert exc.value.status_code == 503
    assert exc.value.type_uri == "/problems/model-artefact-not-found"


def test_pit_features_unavailable() -> None:
    store = InMemoryPitFeatureStore([])
    with pytest.raises(PitFeaturesUnavailableError) as exc:
        store.get_pit_features("mth_missing", None)
    assert exc.value.status_code == 422
    assert exc.value.type_uri == "/problems/pit-features-unavailable"


def test_cutoff_after_kickoff_is_temporal_leakage() -> None:
    store = InMemoryPitFeatureStore([_snapshot()])
    with pytest.raises(TemporalLeakageError) as exc:
        store.get_pit_features("mth_unit", LIVE_KICKOFF + timedelta(seconds=1))
    assert exc.value.status_code == 409
    assert exc.value.type_uri == "/problems/temporal-leakage"


def test_cutoff_before_kickoff_has_no_snapshot() -> None:
    store = InMemoryPitFeatureStore([_snapshot()])
    with pytest.raises(PitFeaturesUnavailableError):
        store.get_pit_features("mth_unit", LIVE_KICKOFF - timedelta(hours=1))


def test_mock_feature_rows_are_refused() -> None:
    store = InMemoryPitFeatureStore([_snapshot(data_mode="mock")])
    with pytest.raises(PitFeaturesUnavailableError, match="non-live"):
        store.get_pit_features("mth_unit", None)


def test_later_match_row_cannot_leak_into_requested_match() -> None:
    _require_live_assets()
    target = _snapshot("mth_early", home=1479.5745333246837, away=1501.3822853628935)
    poison = _snapshot(
        "mth_later",
        event_at=LIVE_KICKOFF + timedelta(days=30),
        home=1900.0,
        away=1100.0,
    )
    store = InMemoryPitFeatureStore([target, poison])
    model = load_football_1x2_model(registry_dir=ARTEFACT_DIR, model_version=CANDIDATE_MODEL_VERSION)
    isolated = InMemoryPitFeatureStore([target])
    clock = Clock(datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    mixed = FootballPredictionService(clock=clock, features=store, model=model).predict("mth_early", None)
    control = FootballPredictionService(clock=clock, features=isolated, model=model).predict("mth_early", None)
    assert mixed.home_probability == control.home_probability
    assert mixed.draw_probability == control.draw_probability
    assert mixed.away_probability == control.away_probability
    assert mixed.model_status == CANDIDATE_STATUS


def test_candidate_artefact_and_reproducible_simplex() -> None:
    _require_live_assets()
    first = load_football_1x2_model(registry_dir=ARTEFACT_DIR, model_version=CANDIDATE_MODEL_VERSION)
    second = load_football_1x2_model(registry_dir=ARTEFACT_DIR, model_version=CANDIDATE_MODEL_VERSION)
    assert first.model_status == CANDIDATE_STATUS
    assert first.model_version == CANDIDATE_MODEL_VERSION
    assert second.model_status != "champion"
    store = ParquetPitFeatureStore(DATASET)
    features = store.get_pit_features(LIVE_MATCH_ID, None)
    assert features.data_mode == "live"
    left = first.predict_1x2(features)
    right = second.predict_1x2(features)
    assert left.as_tuple() == right.as_tuple()
    assert left.total() == pytest.approx(1.0, abs=1e-12)
    clock = Clock(datetime(2026, 9, 9, 18, 0, tzinfo=UTC))
    service = FootballPredictionService(clock=clock, features=store, model=first)
    payload = service.predict(LIVE_MATCH_ID, LIVE_KICKOFF)
    assert payload.model_status == "candidate"
    assert payload.home_probability + payload.draw_probability + payload.away_probability == pytest.approx(1.0)
    dumped = payload.model_dump()
    assert "expected_value" not in dumped
    assert "edge" not in dumped
    assert "odds" not in dumped


def test_pit_snapshot_cannot_carry_post_match_labels() -> None:
    forbidden = {"target", "home_win", "draw", "away_win", "y", "score", "standing"}
    assert forbidden.isdisjoint(PitEloFeatures.__dataclass_fields__)
    assert set(ELO_FEATURES).issubset(PitEloFeatures.__dataclass_fields__)


def test_parquet_store_exposes_only_pre_kickoff_elo() -> None:
    _require_live_assets()
    features = ParquetPitFeatureStore(DATASET).get_pit_features(LIVE_MATCH_ID, LIVE_KICKOFF)
    assert features.data_mode == "live"
    assert features.cutoff_policy == CUTOFF_POLICY_PRE_KICKOFF
    assert features.dataset_version == "football-1x2-history-0.3"
    assert features.feature_schema_version == "football-1x2-features-0.3"
    assert not hasattr(features, "target")
    assert not hasattr(features, "home_win")


def test_candidate_card_matches_runtime_dataset_hash() -> None:
    _require_live_assets()
    card_path = ARTEFACT_DIR / CANDIDATE_MODEL_VERSION / "registry.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    assert card["status"] == "candidate"
    assert card["model_version"] == CANDIDATE_MODEL_VERSION
    assert card["dataset_version"] == "football-1x2-history-0.3"
    assert card["feature_schema_version"] == "football-1x2-features-0.3"
    assert digest == card["dataset_sha256"]
