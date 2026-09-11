from __future__ import annotations

from datetime import UTC, datetime

from predicta_ml.oos.dataset import OosMatch
from predicta_ml.oos.errors import OosIdentityError, OosLeakageError, OosProtocolError
from predicta_ml.oos.odds import OddsQuote, assert_no_snapshot_ambiguity, assert_odds_pit_safe
from predicta_ml.oos.predictions import FrozenPrediction
from predicta_ml.oos.provenance import ModelProvenance


def assert_prediction_cutoff(match: OosMatch) -> None:
    if match.cutoff_at.tzinfo is None or match.kickoff_at.tzinfo is None:
        raise OosProtocolError("cutoff_at and kickoff_at must be timezone-aware UTC.")
    cutoff = match.cutoff_at.astimezone(UTC)
    kickoff = match.kickoff_at.astimezone(UTC)
    if cutoff > kickoff:
        raise OosLeakageError(
            f"Prediction cutoff {cutoff.isoformat()} is after kickoff {kickoff.isoformat()}."
        )
    if cutoff != kickoff:
        raise OosLeakageError(
            "Frozen PIT policy is pre_kickoff; cutoff_at must equal kickoff_at. "
            f"Got cutoff={cutoff.isoformat()} kickoff={kickoff.isoformat()}."
        )


def assert_feature_observation_pit(
    *,
    match_id: str,
    cutoff_at: datetime,
    feature_available_at: datetime | None,
    feature_event_at: datetime | None,
) -> None:
    cutoff = cutoff_at.astimezone(UTC)
    if feature_available_at is not None and feature_available_at.astimezone(UTC) >= cutoff:
        raise OosLeakageError(
            f"Feature available_at for {match_id} is not strictly before cutoff {cutoff.isoformat()}."
        )
    if feature_event_at is not None and feature_event_at.astimezone(UTC) >= cutoff:
        raise OosLeakageError(
            f"Feature event_at for {match_id} is not strictly before cutoff {cutoff.isoformat()}."
        )


def assert_training_window(provenance: ModelProvenance, event_at: datetime) -> None:
    if event_at.astimezone(UTC) >= provenance.latest_training_event_at_exclusive:
        raise OosLeakageError(
            "Training contains an event at or after the training cutoff "
            f"{provenance.latest_training_event_at_exclusive.isoformat()}."
        )


def assert_calibration_window(provenance: ModelProvenance, event_at: datetime) -> None:
    if event_at.astimezone(UTC) >= provenance.latest_calibration_event_at_exclusive:
        raise OosLeakageError(
            "Calibration contains an event at or after the calibration cutoff "
            f"{provenance.latest_calibration_event_at_exclusive.isoformat()}."
        )


def assert_artefact_compatible_with_oos(provenance: ModelProvenance, oos_start: datetime) -> None:
    if oos_start.astimezone(UTC) < provenance.earliest_legitimate_oos:
        raise OosLeakageError(
            "Model artefact provenance is incompatible with the proposed OOS period "
            f"{oos_start.isoformat()} < {provenance.earliest_legitimate_oos.isoformat()}."
        )


def assert_prediction_does_not_use_outcome(prediction: FrozenPrediction, match: OosMatch) -> None:
    if prediction.match_id != match.match_id:
        raise OosIdentityError("Prediction match_id does not match the OOS match.")
    # Frozen Elo uses only elo_diff. Outcome is attached after the fact.
    if match.outcome not in {"HOME", "DRAW", "AWAY"}:
        raise OosProtocolError("Cannot evaluate an unfinished match as OOS.")


def audit_match_quotes(match: OosMatch, quotes: tuple[OddsQuote, ...]) -> None:
    assert_prediction_cutoff(match)
    assert_no_snapshot_ambiguity(quotes)
    for quote in quotes:
        if quote.match_id != match.match_id:
            continue
        if quote.available_at <= match.cutoff_at:
            assert_odds_pit_safe(quote, cutoff_at=match.cutoff_at, kickoff_at=match.kickoff_at)
