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
