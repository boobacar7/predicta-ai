from __future__ import annotations

from dataclasses import dataclass

from predicta_ml.constants import FEATURE_SCHEMA_VERSION


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    dtype: str
    source: str
    pit_available: bool
    used_by: tuple[str, ...]
    notes: str


FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "home_elo_pre",
        "float64",
        "reconstruct_pre_match_elo snapshot at event_at",
        True,
        ("elo", "xgboost", "lightgbm"),
        "Global inter-competition Elo before kickoff. Initial 1500.",
    ),
    FeatureSpec(
        "away_elo_pre",
        "float64",
        "reconstruct_pre_match_elo snapshot at event_at",
        True,
        ("elo", "xgboost", "lightgbm"),
        "Global inter-competition Elo before kickoff. Initial 1500.",
    ),
    FeatureSpec(
        "elo_diff",
        "float64",
        "home_elo_pre - away_elo_pre",
        True,
        ("elo", "xgboost", "lightgbm"),
        "Does not include the +80 home-advantage term used at Elo update time.",
    ),
    FeatureSpec(
        "elo_available",
        "int64",
        "1 if both pre-match Elo ratings exist",
        True,
        (),
        "Constant 1 on football-1x2-history-0.3. Dropped from estimators (zero variance).",
    ),
    FeatureSpec(
        "home_form_5",
        "int64",
        "points in last 5 PIT-valid matches (3/1/0)",
        True,
        ("xgboost", "lightgbm"),
        "0 when the window is empty; use home_form_5_available to distinguish cold start.",
    ),
    FeatureSpec(
        "away_form_5",
        "int64",
        "points in last 5 PIT-valid matches (3/1/0)",
        True,
        ("xgboost", "lightgbm"),
        "0 when the window is empty; use away_form_5_available to distinguish cold start.",
    ),
    FeatureSpec(
        "home_form_10",
        "int64",
        "points in last 10 PIT-valid matches (3/1/0)",
        True,
        ("xgboost", "lightgbm"),
        "0 when the window is empty; use home_form_10_available to distinguish cold start.",
    ),
    FeatureSpec(
        "away_form_10",
        "int64",
        "points in last 10 PIT-valid matches (3/1/0)",
        True,
        ("xgboost", "lightgbm"),
        "0 when the window is empty; use away_form_10_available to distinguish cold start.",
    ),
    FeatureSpec(
        "home_form_5_available",
        "int64",
        "1 if home has >= 5 prior PIT-valid matches",
        True,
        ("poisson", "xgboost", "lightgbm"),
        "Availability flag. Not a future-looking standing.",
    ),
    FeatureSpec(
        "away_form_5_available",
        "int64",
        "1 if away has >= 5 prior PIT-valid matches",
        True,
        ("poisson", "xgboost", "lightgbm"),
        "Availability flag. Not a future-looking standing.",
    ),
    FeatureSpec(
        "home_form_10_available",
        "int64",
        "1 if home has >= 10 prior PIT-valid matches",
        True,
        ("xgboost", "lightgbm"),
        "Availability flag.",
    ),
    FeatureSpec(
        "away_form_10_available",
        "int64",
        "1 if away has >= 10 prior PIT-valid matches",
        True,
        ("xgboost", "lightgbm"),
        "Availability flag.",
    ),
    FeatureSpec(
        "home_goals_for_5",
        "int64",
        "goals scored by home team in last 5 PIT-valid matches",
        True,
        ("poisson", "xgboost", "lightgbm"),
        "Attack proxy. Window excludes the target match.",
    ),
    FeatureSpec(
        "home_goals_against_5",
        "int64",
        "goals conceded by home team in last 5 PIT-valid matches",
        True,
        ("poisson", "xgboost", "lightgbm"),
        "Defence proxy. Window excludes the target match.",
    ),
    FeatureSpec(
        "home_goals_for_10",
        "int64",
        "goals scored by home team in last 10 PIT-valid matches",
        True,
        ("xgboost", "lightgbm"),
        "Longer attack window.",
    ),
    FeatureSpec(
        "home_goals_against_10",
        "int64",
        "goals conceded by home team in last 10 PIT-valid matches",
        True,
        ("xgboost", "lightgbm"),
        "Longer defence window.",
    ),
    FeatureSpec(
        "away_goals_for_5",
        "int64",
        "goals scored by away team in last 5 PIT-valid matches",
        True,
        ("poisson", "xgboost", "lightgbm"),
        "Attack proxy. Window excludes the target match.",
    ),
    FeatureSpec(
        "away_goals_against_5",
        "int64",
        "goals conceded by away team in last 5 PIT-valid matches",
        True,
        ("poisson", "xgboost", "lightgbm"),
        "Defence proxy. Window excludes the target match.",
    ),
    FeatureSpec(
        "away_goals_for_10",
        "int64",
        "goals scored by away team in last 10 PIT-valid matches",
        True,
        ("xgboost", "lightgbm"),
        "Longer attack window.",
    ),
    FeatureSpec(
        "away_goals_against_10",
        "int64",
        "goals conceded by away team in last 10 PIT-valid matches",
        True,
        ("xgboost", "lightgbm"),
        "Longer defence window.",
    ),
    FeatureSpec(
        "h2h_home_wins",
        "int64",
        "prior H2H wins for the current home side",
        True,
        ("xgboost", "lightgbm"),
        "Perspective of the scheduled home team. Requires PIT-valid prior meetings.",
    ),
    FeatureSpec(
        "h2h_draws",
        "int64",
        "prior H2H draws between the two clubs",
        True,
        ("xgboost", "lightgbm"),
        "Independent of home/away orientation of the prior meeting.",
    ),
    FeatureSpec(
        "h2h_away_wins",
        "int64",
        "prior H2H wins for the current away side",
        True,
        ("xgboost", "lightgbm"),
        "Perspective of the scheduled away team.",
    ),
    FeatureSpec(
        "h2h_available",
        "int64",
        "1 if h2h_matches >= 2",
        True,
        ("xgboost", "lightgbm"),
        "Sparse on 0.3 (2168/5729). Zero means insufficient PIT H2H, not a missing JSON null.",
    ),
    FeatureSpec(
        "h2h_matches",
        "int64",
        "count of PIT-valid prior meetings",
        True,
        ("xgboost", "lightgbm"),
        "Target match excluded.",
    ),
    FeatureSpec(
        "home_matches_played",
        "int64",
        "count of PIT-valid prior matches for the home club",
        True,
        ("xgboost", "lightgbm"),
        "All competitions share the canonical team id.",
    ),
    FeatureSpec(
        "away_matches_played",
        "int64",
        "count of PIT-valid prior matches for the away club",
        True,
        ("xgboost", "lightgbm"),
        "All competitions share the canonical team id.",
    ),
)

FEATURE_SCHEMA: tuple[str, ...] = tuple(item.name for item in FEATURE_SPECS)
FEATURE_SPEC_MAP: dict[str, FeatureSpec] = {item.name: item for item in FEATURE_SPECS}

BOOSTING_FEATURES: tuple[str, ...] = tuple(item.name for item in FEATURE_SPECS if item.name != "elo_available")
ELO_FEATURES: tuple[str, ...] = ("home_elo_pre", "away_elo_pre", "elo_diff")
POISSON_FEATURES: tuple[str, ...] = (
    "home_goals_for_5",
    "home_goals_against_5",
    "away_goals_for_5",
    "away_goals_against_5",
    "home_form_5_available",
    "away_form_5_available",
)


def schema_version() -> str:
    return FEATURE_SCHEMA_VERSION
