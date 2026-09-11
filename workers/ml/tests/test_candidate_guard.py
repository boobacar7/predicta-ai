from __future__ import annotations

import json
from pathlib import Path

from predicta_ml.constants import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS, ELO_HOME_ADVANTAGE, ELO_K

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CLI = ROOT / "src" / "predicta_ml" / "cli.py"
ELO_CANDIDATE = ROOT / "src" / "predicta_ml" / "validation" / "elo_candidate.py"


def test_candidate_constants_are_not_production() -> None:
    assert CANDIDATE_MODEL_VERSION == "football-elo-v1-candidate"
    assert CANDIDATE_STATUS == "candidate"
    assert CANDIDATE_STATUS != "champion"
    assert CANDIDATE_STATUS != "production"
    assert ELO_K == 20.0
    assert ELO_HOME_ADVANTAGE == 80.0


def test_committed_candidate_reports_are_not_promoted() -> None:
    summary = json.loads((REPORTS / f"{CANDIDATE_MODEL_VERSION}.summary.json").read_text(encoding="utf-8"))
    registry = json.loads((REPORTS / f"{CANDIDATE_MODEL_VERSION}.registry.json").read_text(encoding="utf-8"))
    assert summary["model_version"] == CANDIDATE_MODEL_VERSION
    assert summary["status"] == CANDIDATE_STATUS
    assert summary["promoted_to_production"] is False
    assert registry["model_version"] == CANDIDATE_MODEL_VERSION
    assert registry["status"] == CANDIDATE_STATUS
    assert registry["status"] != "champion"
    assert registry["status"] != "production"


def test_validate_elo_cannot_auto_promote_to_production() -> None:
    source = ELO_CANDIDATE.read_text(encoding="utf-8")
    cli = CLI.read_text(encoding="utf-8")
    assert "promoted_to_production=True" not in source
    assert "promoted_to_production: True" not in source
    assert '"promoted_to_production": True' not in source
    assert "promoted_to_production\": false" in source or "promoted_to_production\": False" in source
    assert 'add_parser("promote"' not in cli
    assert 'add_parser("publish"' not in cli
    assert "no production promotion" in cli
