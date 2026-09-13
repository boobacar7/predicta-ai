from pathlib import Path
from unittest.mock import MagicMock

import pytest

from predicta_ingestion.persistence.schema import (
    PRE_ODDS_HISTORY_REVISIONS,
    REQUIRED_ODDS_HISTORY_REVISION,
    REQUIRED_ODDS_SNAPSHOT_COLUMNS,
    OddsHistorySchemaError,
    require_odds_history_schema,
)


def test_odds_history_migration_source_covers_append_only_contract() -> None:
    migration = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "0004_odds_history.py"
    ).read_text(encoding="utf-8")
    assert REQUIRED_ODDS_HISTORY_REVISION == "0004_odds_history"
    assert 'revision: str = "0004_odds_history"' in migration
    assert "provider_id" in migration
    for column in REQUIRED_ODDS_SNAPSHOT_COLUMNS:
        assert column in migration
    assert "COALESCE(data_mode, 'mock')" in migration
    assert "ck_odds_snapshots_data_mode" in migration
    assert "data_mode IN ('mock', 'live')" in migration
    assert "ck_odds_snapshots_available_at" in migration
    assert "available_at >= collected_at" in migration
    assert "uq_odds_snapshot_provider_id" in migration
    assert "uq_odds_snapshot_selection" in migration
    assert "DELETE FROM odds_selections AS duplicate" in migration
    assert "ON CONFLICT" not in migration
    assert "op.drop_table" not in migration
    assert "0003_league_competition_identity" in PRE_ODDS_HISTORY_REVISIONS
    assert REQUIRED_ODDS_HISTORY_REVISION not in PRE_ODDS_HISTORY_REVISIONS


def _schema_engine(*, revision: str | None, columns: set[str]) -> MagicMock:
    connection = MagicMock()

    def execute(statement: object, *args: object, **kwargs: object) -> MagicMock:
        sql = str(statement)
        result = MagicMock()
        if "alembic_version" in sql:
            result.scalar.return_value = revision
            return result
        result.__iter__.return_value = iter((name,) for name in columns)
        return result

    connection.execute.side_effect = execute
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = False
    return engine


def test_odds_history_schema_accepts_later_alembic_head() -> None:
    engine = _schema_engine(
        revision="0005_users_sessions",
        columns=set(REQUIRED_ODDS_SNAPSHOT_COLUMNS),
    )
    assert require_odds_history_schema(engine) == "0005_users_sessions"


def test_odds_history_schema_still_accepts_0004_head() -> None:
    engine = _schema_engine(
        revision="0004_odds_history",
        columns=set(REQUIRED_ODDS_SNAPSHOT_COLUMNS),
    )
    assert require_odds_history_schema(engine) == "0004_odds_history"


def test_odds_history_schema_refuses_pre_0004_revision() -> None:
    engine = _schema_engine(
        revision="0003_league_competition_identity",
        columns=set(REQUIRED_ODDS_SNAPSHOT_COLUMNS),
    )
    with pytest.raises(OddsHistorySchemaError, match="0003_league_competition_identity"):
        require_odds_history_schema(engine)


def test_odds_history_schema_refuses_later_head_missing_0004_columns() -> None:
    engine = _schema_engine(
        revision="0005_users_sessions",
        columns={"available_at", "collected_at", "data_mode", "source"},
    )
    with pytest.raises(OddsHistorySchemaError, match="provider_id"):
        require_odds_history_schema(engine)
