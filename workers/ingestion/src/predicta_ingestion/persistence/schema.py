from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

REQUIRED_ODDS_HISTORY_REVISION = "0004_odds_history"
REQUIRED_ODDS_SNAPSHOT_COLUMNS = frozenset(
    {
        "provider_id",
        "available_at",
        "collected_at",
        "data_mode",
        "source",
    }
)


class OddsHistorySchemaError(RuntimeError):
    """Raised when the shared API schema is missing Alembic 0004_odds_history."""


def require_odds_history_schema(engine: Engine) -> str:
    """Fail fast before live odds persist if 0004 is not applied.

    This inspects an already-configured runtime database. It is not a CI
    Postgres fixture and does not invent schema.
    """
    with engine.connect() as connection:
        try:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except Exception as exc:
            raise OddsHistorySchemaError(
                "Odds persistence requires Alembic "
                f"{REQUIRED_ODDS_HISTORY_REVISION}, but alembic_version is unreadable. "
                "Run: cd apps/api && alembic upgrade head"
            ) from exc
        if revision != REQUIRED_ODDS_HISTORY_REVISION:
            raise OddsHistorySchemaError(
                "Odds persistence requires Alembic "
                f"{REQUIRED_ODDS_HISTORY_REVISION}; current revision is {revision!r}. "
                "Run: cd apps/api && alembic upgrade head"
            )
        columns = {
            str(row[0])
            for row in connection.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'odds_snapshots'
                    """
                )
            )
        }
        missing = sorted(REQUIRED_ODDS_SNAPSHOT_COLUMNS - columns)
        if missing:
            raise OddsHistorySchemaError(
                "odds_snapshots is missing 0004 columns: "
                + ", ".join(missing)
                + ". Run: cd apps/api && alembic upgrade head"
            )
    return REQUIRED_ODDS_HISTORY_REVISION
