"""Strengthen append-only odds snapshot provenance.

Revision ID: 0004_odds_history
Revises: 0003_league_competition_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_odds_history"
down_revision: str | None = "0003_league_competition_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "odds_snapshots",
        sa.Column("provider_id", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE odds_snapshots
        SET provider_id = provider || ':' || id,
            collected_at = COALESCE(collected_at, observed_at),
            available_at = COALESCE(available_at, collected_at, observed_at),
            source = COALESCE(source, provider)
        """
    )
    op.alter_column("odds_snapshots", "provider_id", nullable=False)
    op.alter_column("odds_snapshots", "collected_at", nullable=False)
    op.alter_column("odds_snapshots", "available_at", nullable=False)
    op.alter_column("odds_snapshots", "source", nullable=False)
    op.alter_column("odds_snapshots", "data_mode", nullable=False)
    op.create_unique_constraint(
        "uq_odds_snapshot_provider_id",
        "odds_snapshots",
        ["provider", "provider_id"],
    )
    op.create_unique_constraint(
        "uq_odds_snapshot_selection",
        "odds_selections",
        ["snapshot_id", "selection"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_odds_snapshot_selection",
        "odds_selections",
        type_="unique",
    )
    op.drop_constraint(
        "uq_odds_snapshot_provider_id",
        "odds_snapshots",
        type_="unique",
    )
    op.alter_column("odds_snapshots", "data_mode", nullable=True)
    op.alter_column("odds_snapshots", "source", nullable=True)
    op.alter_column("odds_snapshots", "available_at", nullable=True)
    op.alter_column("odds_snapshots", "collected_at", nullable=True)
    op.drop_column("odds_snapshots", "provider_id")
