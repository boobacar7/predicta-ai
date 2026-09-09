"""Initial canonical sports intelligence schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sports",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "leagues",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("sport_id", sa.String(128), sa.ForeignKey("sports.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(128), nullable=False),
        sa.Column("season", sa.String(32), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_leagues_sport_id", "leagues", ["sport_id"])
    op.create_table(
        "teams",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("sport_id", sa.String(128), sa.ForeignKey("sports.id"), nullable=False),
        sa.Column("league_id", sa.String(128), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(128), nullable=False),
        sa.Column("abbreviation", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_teams_sport_id", "teams", ["sport_id"])
    op.create_index("ix_teams_league_id", "teams", ["league_id"])
    op.create_table(
        "players",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("sport_id", sa.String(128), sa.ForeignKey("sports.id"), nullable=False),
        sa.Column("team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.String(128), nullable=True),
        sa.Column("country", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_players_sport_id", "players", ["sport_id"])
    op.create_index("ix_players_team_id", "players", ["team_id"])
    op.create_table(
        "provider_entity_maps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("provider_entity_id", sa.String(255), nullable=False),
        sa.Column("canonical_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "entity_type", "provider_entity_id", name="uq_provider_entity"),
    )
    op.create_index("ix_provider_entity_maps_canonical_id", "provider_entity_maps", ["canonical_id"])
    op.create_table(
        "matches",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("sport_id", sa.String(128), sa.ForeignKey("sports.id"), nullable=False),
        sa.Column("league_id", sa.String(128), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("home_team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("away_team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("venue", sa.String(255), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_matches_sport_id", "matches", ["sport_id"])
    op.create_index("ix_matches_league_id", "matches", ["league_id"])
    op.create_index("ix_matches_kickoff_at", "matches", ["kickoff_at"])
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_table(
        "match_events",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("match_id", sa.String(128), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(128), nullable=True),
    )
    op.create_index("ix_match_events_match_id", "match_events", ["match_id"])
    op.create_table(
        "match_statistics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(128), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("stat_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("home_value", sa.Numeric(18, 8), nullable=True),
        sa.Column("away_value", sa.Numeric(18, 8), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_match_statistics_match_id", "match_statistics", ["match_id"])
    op.create_table(
        "team_statistics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("season", sa.String(32), nullable=False),
        sa.Column("stat_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("value", sa.Numeric(18, 8), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_team_statistics_team_id", "team_statistics", ["team_id"])
    op.create_table(
        "player_statistics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.String(128), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("season", sa.String(32), nullable=False),
        sa.Column("stat_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("value", sa.Numeric(18, 8), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_player_statistics_player_id", "player_statistics", ["player_id"])
    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("match_id", sa.String(128), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("market", sa.String(64), nullable=False),
        sa.Column("bookmaker", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("overround", sa.Numeric(18, 10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_odds_snapshots_match_id", "odds_snapshots", ["match_id"])
    op.create_index("ix_odds_snapshots_observed_at", "odds_snapshots", ["observed_at"])
    op.create_table(
        "odds_selections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(128), sa.ForeignKey("odds_snapshots.id"), nullable=False),
        sa.Column("selection", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("decimal_odds", sa.Numeric(18, 10), nullable=True),
        sa.Column("implied_probability_raw", sa.Numeric(18, 10), nullable=True),
        sa.Column("no_vig_probability", sa.Numeric(18, 10), nullable=True),
        sa.CheckConstraint("decimal_odds IS NULL OR decimal_odds > 1", name="ck_odds_gt_one"),
    )
    op.create_index("ix_odds_selections_snapshot_id", "odds_selections", ["snapshot_id"])
    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("family", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False, unique=True),
        sa.Column("calibrator_version", sa.String(64), nullable=False),
        sa.Column("feature_set_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "model_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_version_id", sa.String(128), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("sport", sa.String(32), nullable=False),
        sa.Column("window_label", sa.String(128), nullable=False),
        sa.Column("accuracy", sa.Numeric(18, 10), nullable=True),
        sa.Column("log_loss", sa.Numeric(18, 10), nullable=True),
        sa.Column("brier_score", sa.Numeric(18, 10), nullable=True),
        sa.Column("ece", sa.Numeric(18, 10), nullable=True),
        sa.Column("theoretical_roi", sa.Numeric(18, 10), nullable=True),
        sa.Column("theoretical_max_drawdown", sa.Numeric(18, 10), nullable=True),
        sa.Column("prediction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "theoretical_max_drawdown IS NULL OR (theoretical_max_drawdown >= -1 AND theoretical_max_drawdown <= 0)",
            name="ck_drawdown_non_positive",
        ),
    )
    op.create_index("ix_model_metrics_model_version_id", "model_metrics", ["model_version_id"])
    op.create_table(
        "predictions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("match_id", sa.String(128), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("model_version_id", sa.String(128), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("market", sa.String(64), nullable=False),
        sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_predictions_match_id", "predictions", ["match_id"])
    op.create_index("ix_predictions_model_version_id", "predictions", ["model_version_id"])
    op.create_table(
        "prediction_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prediction_id", sa.String(128), sa.ForeignKey("predictions.id"), nullable=False),
        sa.Column("selection", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("model_probability", sa.Numeric(18, 10), nullable=True),
        sa.Column("calibrated_probability", sa.Numeric(18, 10), nullable=True),
        sa.CheckConstraint(
            "model_probability IS NULL OR (model_probability >= 0 AND model_probability <= 1)",
            name="ck_model_probability",
        ),
        sa.CheckConstraint(
            "calibrated_probability IS NULL OR (calibrated_probability >= 0 AND calibrated_probability <= 1)",
            name="ck_calibrated_probability",
        ),
    )
    op.create_index("ix_prediction_outcomes_prediction_id", "prediction_outcomes", ["prediction_id"])
    op.create_table(
        "prediction_factors",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("prediction_id", sa.String(128), sa.ForeignKey("predictions.id"), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("weight", sa.String(16), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
    )
    op.create_index("ix_prediction_factors_prediction_id", "prediction_factors", ["prediction_id"])
    op.create_table(
        "published_picks",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("match_id", sa.String(128), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("prediction_id", sa.String(128), sa.ForeignKey("predictions.id"), nullable=True),
        sa.Column("market", sa.String(64), nullable=False),
        sa.Column("selection", sa.String(64), nullable=False),
        sa.Column("selection_label", sa.String(128), nullable=False),
        sa.Column("calibrated_probability", sa.Numeric(18, 10), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("criteria", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_published_picks_match_id", "published_picks", ["match_id"])
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("match_id", sa.String(128), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("fact_pack", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("llm_model", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_analyses_match_id", "ai_analyses", ["match_id"])


def downgrade() -> None:
    for table in [
        "ai_analyses",
        "published_picks",
        "prediction_factors",
        "prediction_outcomes",
        "predictions",
        "model_metrics",
        "model_versions",
        "odds_selections",
        "odds_snapshots",
        "player_statistics",
        "team_statistics",
        "match_statistics",
        "match_events",
        "matches",
        "provider_entity_maps",
        "players",
        "teams",
        "leagues",
        "sports",
    ]:
        op.drop_table(table)
