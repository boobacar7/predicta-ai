from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_heads_data_ingestion() -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "alembic"))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    assert [item.revision for item in revisions] == [
        "0004_odds_history",
        "0003_league_competition_identity",
        "0002_data_ingestion",
        "0001_initial",
    ]
    assert script.get_current_head() == "0004_odds_history"


def test_odds_history_revision_is_append_only_and_backfills_provenance() -> None:
    migration = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0004_odds_history.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "0004_odds_history"' in migration
    assert "provider_id" in migration
    assert "COALESCE(data_mode, 'mock')" in migration
    assert "COALESCE(available_at, collected_at, observed_at)" in migration
    assert "ck_odds_snapshots_data_mode" in migration
    assert "data_mode IN ('mock', 'live')" in migration
    assert "ck_odds_snapshots_available_at" in migration
    assert "available_at >= collected_at" in migration
    assert "uq_odds_snapshot_provider_id" in migration
    assert "uq_odds_snapshot_selection" in migration
    assert "DELETE FROM odds_selections AS duplicate" in migration
    update_block = migration.split('op.alter_column("odds_snapshots", "data_mode"', maxsplit=1)[0]
    assert "COALESCE(data_mode, 'mock')" in update_block
    assert "op.drop_table" not in migration
    assert "UPDATE odds_snapshots SET decimal" not in migration
