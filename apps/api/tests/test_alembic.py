from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_initial_revision() -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "alembic"))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    assert len(revisions) == 1
    assert revisions[0].revision == "0001_initial"
    assert script.get_current_head() == "0001_initial"
