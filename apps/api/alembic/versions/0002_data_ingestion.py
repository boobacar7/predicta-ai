"""Data ingestion provenance, raw metadata, standings, injuries and lineups.

Revision ID: 0002_data_ingestion
Revises: 0001_initial
Create Date: 2026-09-09

Expand-only: adds tables and nullable/defaulted columns. No drops of existing
business data. Raw provider bodies stay outside PostgreSQL; this revision
stores metadata, identity provenance and historical snapshots required for
point-in-time feature reads.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_data_ingestion"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "raw_payloads",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("sport_code", sa.String(32), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("provider_request_key", sa.String(255), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("storage_uri", sa.String(1024), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_mode", sa.String(16), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "checksum_sha256", name="uq_raw_payload_checksum"),
    )
    op.create_index("ix_raw_payloads_provider", "raw_payloads", ["provider"])
    op.create_index("ix_raw_payloads_collected_at", "raw_payloads", ["collected_at"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.String(255), nullable=True),
        sa.Column("checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("records_read", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_quarantined", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("data_mode", sa.String(16), nullable=False),
    )

    op.create_table(
        "quarantine_records",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("run_id", sa.String(128), sa.ForeignKey("ingestion_runs.id"), nullable=True),
        sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("provider_entity_id", sa.String(255), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("payload_excerpt", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_mode", sa.String(16), nullable=False),
    )
    op.create_index("ix_quarantine_records_run_id", "quarantine_records", ["run_id"])

    op.add_column("provider_entity_maps", sa.Column("sport_id", sa.String(128), sa.ForeignKey("sports.id"), nullable=True))
    op.add_column(
        "provider_entity_maps",
        sa.Column("resolution_method", sa.String(32), nullable=False, server_default="exact_id"),
    )
    op.add_column("provider_entity_maps", sa.Column("confidence", sa.Numeric(8, 6), nullable=True))
    op.add_column(
        "provider_entity_maps",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.add_column("matches", sa.Column("source", sa.String(128), nullable=True))
    op.add_column("matches", sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("matches", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("matches", sa.Column("data_mode", sa.String(16), nullable=True))
    op.add_column("matches", sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True))

    op.add_column("match_events", sa.Column("player_id", sa.String(128), sa.ForeignKey("players.id"), nullable=True))
    op.add_column("match_events", sa.Column("event_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("match_events", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("match_events", sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("match_events", sa.Column("provider", sa.String(128), nullable=True))
    op.add_column("match_events", sa.Column("freshness", sa.String(32), nullable=True))
    op.add_column("match_events", sa.Column("data_mode", sa.String(16), nullable=True))
    op.add_column("match_events", sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True))

    for table in ("match_statistics", "team_statistics", "player_statistics"):
        op.add_column(table, sa.Column("provider", sa.String(128), nullable=True))
        op.add_column(table, sa.Column("as_of", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("freshness", sa.String(32), nullable=True))
        op.add_column(table, sa.Column("data_mode", sa.String(16), nullable=True))
        op.add_column(table, sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True))

    op.create_index("ix_team_statistics_as_of", "team_statistics", ["as_of"])
    op.create_index("ix_player_statistics_as_of", "player_statistics", ["as_of"])

    op.add_column("odds_snapshots", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("odds_snapshots", sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("odds_snapshots", sa.Column("source", sa.String(128), nullable=True))
    op.add_column("odds_snapshots", sa.Column("freshness", sa.String(32), nullable=True))
    op.add_column("odds_snapshots", sa.Column("data_mode", sa.String(16), nullable=True))
    op.add_column("odds_snapshots", sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True))
    op.create_unique_constraint(
        "uq_odds_snapshot_natural",
        "odds_snapshots",
        ["provider", "bookmaker", "match_id", "market", "observed_at"],
    )

    op.create_table(
        "standings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("league_id", sa.String(128), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("season", sa.String(32), nullable=False),
        sa.Column("team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("played", sa.Integer(), nullable=True),
        sa.Column("won", sa.Integer(), nullable=True),
        sa.Column("drawn", sa.Integer(), nullable=True),
        sa.Column("lost", sa.Integer(), nullable=True),
        sa.Column("goals_for", sa.Integer(), nullable=True),
        sa.Column("goals_against", sa.Integer(), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness", sa.String(32), nullable=True),
        sa.Column("data_mode", sa.String(16), nullable=False),
        sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True),
        sa.UniqueConstraint("league_id", "season", "team_id", "as_of", "provider", name="uq_standing_snapshot"),
    )
    op.create_index("ix_standings_league_id", "standings", ["league_id"])
    op.create_index("ix_standings_team_id", "standings", ["team_id"])
    op.create_index("ix_standings_as_of", "standings", ["as_of"])

    op.create_table(
        "injuries",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("provider_injury_id", sa.String(255), nullable=False),
        sa.Column("sport_id", sa.String(128), sa.ForeignKey("sports.id"), nullable=False),
        sa.Column("player_id", sa.String(128), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness", sa.String(32), nullable=True),
        sa.Column("data_mode", sa.String(16), nullable=False),
        sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True),
        sa.UniqueConstraint("provider", "provider_injury_id", name="uq_injury_provider"),
    )
    op.create_index("ix_injuries_player_id", "injuries", ["player_id"])
    op.create_index("ix_injuries_team_id", "injuries", ["team_id"])

    op.create_table(
        "lineups",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("match_id", sa.String(128), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("team_id", sa.String(128), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("formation", sa.String(32), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness", sa.String(32), nullable=True),
        sa.Column("data_mode", sa.String(16), nullable=False),
        sa.Column("raw_payload_id", sa.String(128), sa.ForeignKey("raw_payloads.id"), nullable=True),
        sa.UniqueConstraint("match_id", "team_id", "observed_at", "provider", name="uq_lineup_snapshot"),
    )
    op.create_index("ix_lineups_match_id", "lineups", ["match_id"])

    op.create_table(
        "lineup_players",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lineup_id", sa.String(128), sa.ForeignKey("lineups.id"), nullable=False),
        sa.Column("player_id", sa.String(128), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("jersey_number", sa.Integer(), nullable=True),
        sa.Column("position", sa.String(64), nullable=True),
    )
    op.create_index("ix_lineup_players_lineup_id", "lineup_players", ["lineup_id"])


def downgrade() -> None:
    op.drop_table("lineup_players")
    op.drop_table("lineups")
    op.drop_table("injuries")
    op.drop_table("standings")
    op.drop_constraint("uq_odds_snapshot_natural", "odds_snapshots", type_="unique")
    for column in ("raw_payload_id", "data_mode", "freshness", "source", "collected_at", "available_at"):
        op.drop_column("odds_snapshots", column)
    for table in ("player_statistics", "team_statistics", "match_statistics"):
        for column in ("raw_payload_id", "data_mode", "freshness", "collected_at", "available_at", "as_of", "provider"):
            op.drop_column(table, column)
    for column in (
        "raw_payload_id",
        "data_mode",
        "freshness",
        "provider",
        "collected_at",
        "available_at",
        "event_at",
        "player_id",
    ):
        op.drop_column("match_events", column)
    for column in ("raw_payload_id", "data_mode", "available_at", "collected_at", "source"):
        op.drop_column("matches", column)
    op.drop_column("provider_entity_maps", "updated_at")
    op.drop_column("provider_entity_maps", "confidence")
    op.drop_column("provider_entity_maps", "resolution_method")
    op.drop_column("provider_entity_maps", "sport_id")
    op.drop_table("quarantine_records")
    op.drop_table("ingestion_runs")
    op.drop_table("raw_payloads")
