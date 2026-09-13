"""Add competition slug and Sportmonks season id on leagues.

Revision ID: 0003_league_competition_identity
Revises: 0002_data_ingestion
Create Date: 2026-09-10

Expand-only. Match rows keep competition_id / season via their league:
slug is the V1 competition id, provider_season_id is the Sportmonks season id.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_league_competition_identity"
down_revision: str | None = "0002_data_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leagues", sa.Column("slug", sa.String(64), nullable=True))
    op.add_column("leagues", sa.Column("provider_season_id", sa.String(64), nullable=True))
    op.create_index("ix_leagues_slug", "leagues", ["slug"])
    op.create_index("ix_leagues_provider_season_id", "leagues", ["provider_season_id"])


def downgrade() -> None:
    op.drop_index("ix_leagues_provider_season_id", table_name="leagues")
    op.drop_index("ix_leagues_slug", table_name="leagues")
    op.drop_column("leagues", "provider_season_id")
    op.drop_column("leagues", "slug")
