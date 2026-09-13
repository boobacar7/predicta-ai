from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from predicta_ml.constants import (
    CALIBRATION_FIT_END,
    CANDIDATE_MODEL_VERSION,
    CANDIDATE_STATUS,
    COMPETITION_ORDER,
    CUTOFF_POLICY,
    DATASET_VERSION,
    FEATURE_SCHEMA_VERSION,
    FINAL_TEST_START,
    FINAL_TRAIN_END,
    MARKET,
    SPORT,
)

VALUE_ENGINE_VERSION = "value-engine-0.1"
AI_PICKS_VERSION = "ai-picks-0.1"
ODDS_SELECTION_POLICY = (
    "Last complete 1X2 snapshot with available_at <= cutoff, ordered by "
    "(available_at, collected_at, snapshot.id). Bookmaker identity is not a "
    "selection criterion; Pinnacle is not preferred."
)
ODDS_PROVIDER = "the-odds-api-v4"
STAKE_UNITS = 1.0
STAKE_POLICY = "fixed_unit_per_opportunity"
MAXIMUM_ODDS_AGE = timedelta(hours=24)
MINIMUM_EDGE = 0.0
MINIMUM_EV = 0.0
MINIMUM_MODEL_PROBABILITY = 0.0
SMALL_SAMPLE_N = 30
ROBUST_PROFITABILITY_N = 250
CUTOFF_EQUALS_KICKOFF = True

TemporalSplit = Literal[
    "final_train",
    "fold_1_validation",
    "fold_2_validation",
    "calibration_fit",
    "calibration_select",
    "final_test",
    "unknown",
]


@dataclass(frozen=True)
class RejectedPeriod:
    name: str
    start: datetime
    end_exclusive: datetime
    temporal_split: TemporalSplit
    reason: str


# Production PIT is pre_kickoff: cutoff_at == kickoff_at. Underlying feature
# observations still satisfy event_at < cutoff and available_at < cutoff.
# OddsService uses available_at <= cutoff. This protocol does not retune PIT.
FROZEN_CUTOFF_POLICY = CUTOFF_POLICY
TRAIN_CUTOFF = FINAL_TRAIN_END
CALIBRATION_CUTOFF = FINAL_TEST_START
OOS_START = FINAL_TEST_START
CANDIDATE_CREATED_AT = datetime(2026, 9, 10, 17, 43, 36, 436814, tzinfo=UTC)
CANDIDATE_CODE_VERSION = "0.1.0+e8b76d7"
CANDIDATE_DATASET_SHA256 = "0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5"

REJECTED_PERIODS: tuple[RejectedPeriod, ...] = (
    RejectedPeriod(
        name="final_train_including_2024_windows",
        start=datetime(2024, 2, 22, tzinfo=UTC),
        end_exclusive=TRAIN_CUTOFF,
        temporal_split="final_train",
        reason=(
            "football-elo-v1-candidate draw transform was fit on final_train "
            "(event_at < 2026-01-01). Windows W01–W03 are inside that partition "
            "and are not OOS for the frozen artefact."
        ),
    ),
    RejectedPeriod(
        name="fold_1_validation",
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end_exclusive=datetime(2025, 7, 1, tzinfo=UTC),
        temporal_split="fold_1_validation",
        reason="Walk-forward fold_1 validation. Not a held-out OOS window for the frozen artefact.",
    ),
    RejectedPeriod(
        name="fold_2_validation",
        start=datetime(2025, 7, 1, tzinfo=UTC),
        end_exclusive=TRAIN_CUTOFF,
        temporal_split="fold_2_validation",
        reason="Walk-forward fold_2 validation. Not a held-out OOS window for the frozen artefact.",
    ),
    RejectedPeriod(
        name="calibration_fit",
        start=TRAIN_CUTOFF,
        end_exclusive=CALIBRATION_FIT_END,
        temporal_split="calibration_fit",
        reason="Sigmoid calibrator was fit on this window. Invalid as OOS for the frozen artefact.",
    ),
    RejectedPeriod(
        name="calibration_select_including_may_2026",
        start=CALIBRATION_FIT_END,
        end_exclusive=CALIBRATION_CUTOFF,
        temporal_split="calibration_select",
        reason=(
            "Sigmoid calibration method was selected on this window (n=263). "
            "May 2026 historical-odds pilots are calibration_select, not OOS."
        ),
    ),
)


COMPETITION_DISPLAY_TO_SLUG: dict[str, str] = {
    "premier-league": "premier-league",
    "Premier League": "premier-league",
    "ligue-1": "ligue-1",
    "Ligue 1": "ligue-1",
    "la-liga": "la-liga",
    "La Liga": "la-liga",
    "bundesliga": "bundesliga",
    "Bundesliga": "bundesliga",
    "serie-a": "serie-a",
    "Serie A": "serie-a",
    "champions-league": "champions-league",
    "Champions League": "champions-league",
    "mls": "mls",
    "MLS": "mls",
    "Major League Soccer": "mls",
}


def normalize_competition(name: str) -> str:
    return COMPETITION_DISPLAY_TO_SLUG.get(name, name)


def classify_event_at(event_at: datetime) -> TemporalSplit:
    instant = event_at.astimezone(UTC)
    if instant < datetime(2025, 1, 1, tzinfo=UTC):
        return "final_train"
    if instant < datetime(2025, 7, 1, tzinfo=UTC):
        return "fold_1_validation"
    if instant < TRAIN_CUTOFF:
        return "fold_2_validation"
    if instant < CALIBRATION_FIT_END:
        return "calibration_fit"
    if instant < CALIBRATION_CUTOFF:
        return "calibration_select"
    return "final_test"


def is_true_oos_event(event_at: datetime) -> bool:
    return event_at.astimezone(UTC) >= OOS_START


def frozen_manifest_constants() -> dict[str, object]:
    return {
        "dataset_version": DATASET_VERSION,
        "model_version": CANDIDATE_MODEL_VERSION,
        "model_status": CANDIDATE_STATUS,
        "promoted_to_production": False,
        "calibration_version": "sigmoid-ovr-platt-on-calibration_fit-selected-on-calibration_select",
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "value_engine_version": VALUE_ENGINE_VERSION,
        "ai_picks_version": AI_PICKS_VERSION,
        "thresholds": {
            "minimum_edge": MINIMUM_EDGE,
            "minimum_ev": MINIMUM_EV,
            "minimum_model_probability": MINIMUM_MODEL_PROBABILITY,
            "maximum_odds_age_seconds": int(MAXIMUM_ODDS_AGE.total_seconds()),
            "optimized_on_oos": False,
        },
        "oos_start": OOS_START.isoformat(),
        "train_cutoff": TRAIN_CUTOFF.isoformat(),
        "calibration_cutoff": CALIBRATION_CUTOFF.isoformat(),
        "cutoff_policy": FROZEN_CUTOFF_POLICY,
        "cutoff_equals_kickoff": CUTOFF_EQUALS_KICKOFF,
        "odds_provider": ODDS_PROVIDER,
        "odds_selection_policy": ODDS_SELECTION_POLICY,
        "sport": SPORT,
        "market": MARKET,
        "competitions": list(COMPETITION_ORDER),
        "stake": STAKE_UNITS,
        "stake_policy": STAKE_POLICY,
    }
