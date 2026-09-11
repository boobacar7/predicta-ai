from pathlib import Path

from predicta_ingestion.persistence.schema import (
    REQUIRED_ODDS_HISTORY_REVISION,
    REQUIRED_ODDS_SNAPSHOT_COLUMNS,
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
