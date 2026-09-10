from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

PACKAGE_VERSION = "0.1.0"
MODEL_VERSION = "football-1x2-model-0.1"
DATASET_VERSION = "football-1x2-history-0.3"
FEATURE_SCHEMA_VERSION = "football-1x2-features-0.3"
CUTOFF_POLICY = "pre_kickoff"
MARKET = "1X2"
SPORT = "football"
RANDOM_SEED = 42
PROBABILITY_CLIP = 1e-15
POISSON_MAX_GOALS = 10
ELO_HOME_ADVANTAGE = 80.0
ELO_SCALE = 400.0
ELO_K = 20.0
ELO_INITIAL = 1500.0
ELO_UPDATE_DELAY_HOURS = 3
ELO_K_GRID: tuple[int, ...] = (10, 15, 20, 25, 30)
ELO_HA_GRID: tuple[int, ...] = (0, 40, 60, 80, 100)
CANDIDATE_MODEL_VERSION = "football-elo-v1-candidate"
CANDIDATE_STATUS = "candidate"
COMPETITION_ORDER: tuple[str, ...] = (
    "premier-league",
    "ligue-1",
    "la-liga",
    "bundesliga",
    "serie-a",
    "champions-league",
    "mls",
)
COLLAPSE_LOG_LOSS_MARGIN = 0.02
ENSEMBLE_MIN_LOG_LOSS_GAIN = 1e-4
ISOTONIC_MIN_ROWS = 200
ISOTONIC_MIN_PER_CLASS = 30
CALIBRATION_BINS = 10

CLASS_LABELS: tuple[str, str, str] = ("HOME", "DRAW", "AWAY")
CLASS_INDEX: dict[str, int] = {"HOME": 0, "DRAW": 1, "AWAY": 2}

IDENTITY_COLUMNS: tuple[str, ...] = (
    "match_id",
    "event_at",
    "home_team_id",
    "away_team_id",
    "competition",
    "competition_id",
    "competition_name",
    "season",
    "season_id",
    "provider",
    "raw_payload_id",
    "data_mode",
    "dataset_version",
    "cutoff_policy",
)
TARGET_COLUMNS: tuple[str, ...] = ("target", "home_win", "draw", "away_win")

# Expanding walk-forward on the development window. Ends are exclusive.
# Final test starts at 2026-07-01 (387 matches through 2026-09-10). June 2026
# has zero finished matches in dataset 0.3.
WALK_FORWARD_BOUNDS: tuple[tuple[str, datetime, datetime, datetime], ...] = (
    (
        "fold_1",
        datetime(2024, 2, 22, tzinfo=UTC),
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 7, 1, tzinfo=UTC),
    ),
    (
        "fold_2",
        datetime(2024, 2, 22, tzinfo=UTC),
        datetime(2025, 7, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
    ),
    (
        "fold_3",
        datetime(2024, 2, 22, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 7, 1, tzinfo=UTC),
    ),
)

FINAL_TRAIN_END = datetime(2026, 1, 1, tzinfo=UTC)
CALIBRATION_FIT_END = datetime(2026, 5, 1, tzinfo=UTC)
FINAL_TEST_START = datetime(2026, 7, 1, tzinfo=UTC)

XGBOOST_PARAMS: dict[str, object] = {
    "objective": "multi:softprob",
    "num_class": 3,
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_lambda": 1.0,
    "tree_method": "hist",
    "random_state": RANDOM_SEED,
    "n_jobs": 1,
    "verbosity": 0,
}

LIGHTGBM_PARAMS: dict[str, object] = {
    "objective": "multiclass",
    "num_class": 3,
    "n_estimators": 200,
    "num_leaves": 16,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 20,
    "reg_lambda": 1.0,
    "random_state": RANDOM_SEED,
    "n_jobs": 1,
    "verbosity": -1,
    "deterministic": True,
    "force_row_wise": True,
}


def default_dataset_path() -> Path:
    return Path(__file__).resolve().parents[3] / "ingestion" / "var" / "football-1x2-history.parquet"


def default_output_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "var"


def default_committed_reports_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "reports"
