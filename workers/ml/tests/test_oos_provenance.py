from __future__ import annotations

from datetime import UTC, datetime

import pytest

from predicta_ml.constants import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS
from predicta_ml.oos.errors import OosProtocolError
from predicta_ml.oos.protocol import CALIBRATION_CUTOFF, OOS_START, TRAIN_CUTOFF, normalize_competition
from predicta_ml.oos.provenance import (
    assert_window_is_oos,
    audit_model_provenance,
    provenance_summary,
    reject_period_if_invalid,
)


def test_audit_reads_committed_registry_not_inferences() -> None:
    provenance = audit_model_provenance()
    assert provenance.model_version == CANDIDATE_MODEL_VERSION
    assert provenance.status == CANDIDATE_STATUS
    assert provenance.promoted_to_production is False
    assert provenance.train_end_exclusive == TRAIN_CUTOFF
    assert provenance.latest_training_event_at_exclusive == datetime(2026, 1, 1, tzinfo=UTC)
    assert provenance.latest_calibration_event_at_exclusive == CALIBRATION_CUTOFF
    assert provenance.earliest_legitimate_oos == OOS_START
    assert provenance.calibration_method == "sigmoid"
    assert provenance.dataset_sha256 == "0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5"
    assert provenance.train_rows == 4094
    assert provenance.calibration_fit_rows == 985
    assert provenance.calibration_select_rows == 263
    assert provenance.test_rows == 387
    assert provenance.hyperparameters["k"] == 20.0
    assert provenance.hyperparameters["home_advantage"] == 80.0


def test_2024_windows_are_rejected_as_oos() -> None:
    provenance = audit_model_provenance()
    with pytest.raises(OosProtocolError, match="before the artefact freeze"):
        assert_window_is_oos(
            start=datetime(2024, 8, 16, tzinfo=UTC),
            end_exclusive=datetime(2024, 10, 1, tzinfo=UTC),
            provenance=provenance,
        )
    reason = reject_period_if_invalid(datetime(2024, 8, 16, 15, tzinfo=UTC), provenance)
    assert reason is not None
    assert "final_train" in reason or "draw transform" in reason


def test_may_2026_calibration_select_is_rejected() -> None:
    provenance = audit_model_provenance()
    with pytest.raises(OosProtocolError, match="before the artefact freeze"):
        assert_window_is_oos(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end_exclusive=datetime(2026, 6, 1, tzinfo=UTC),
            provenance=provenance,
        )
    reason = reject_period_if_invalid(datetime(2026, 5, 15, 15, tzinfo=UTC), provenance)
    assert reason is not None
    assert "calibration" in reason.lower() or "selected" in reason.lower()


def test_valid_oos_window_starts_at_freeze() -> None:
    provenance = audit_model_provenance()
    assert_window_is_oos(
        start=OOS_START,
        end_exclusive=datetime(2026, 9, 10, 2, 30, 1, tzinfo=UTC),
        provenance=provenance,
    )
    assert reject_period_if_invalid(datetime(2026, 7, 1, tzinfo=UTC), provenance) is None
    summary = provenance_summary(provenance)
    assert summary["earliest_legitimate_oos"] == OOS_START.isoformat()
    names = {item["name"] for item in summary["rejected_periods"]}
    assert "final_train_including_2024_windows" in names
    assert "calibration_select_including_may_2026" in names


def test_competition_display_names_map_to_slugs() -> None:
    assert normalize_competition("Premier League") == "premier-league"
    assert normalize_competition("Ligue 1") == "ligue-1"
    assert normalize_competition("La Liga") == "la-liga"
    assert normalize_competition("Bundesliga") == "bundesliga"
    assert normalize_competition("Serie A") == "serie-a"
    assert normalize_competition("Champions League") == "champions-league"
    assert normalize_competition("Major League Soccer") == "mls"
    assert normalize_competition("Test League") == "Test League"
