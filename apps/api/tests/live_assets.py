from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
PIT_DATASET = REPO / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
CANDIDATE_ARTEFACT = REPO / "workers" / "ml" / "var" / "registry" / "football-elo-v1-candidate" / "artefact.joblib"
RAW_ARCHIVE = REPO / "workers" / "ingestion" / "var" / "raw"

_SKIP_REASON = (
    "gitignored PIT parquet / football-elo-v1-candidate artefact / raw archive are absent; "
    "CI does not download live sports data"
)


def pit_dataset_available() -> bool:
    return PIT_DATASET.is_file()


def live_assets_available() -> bool:
    return pit_dataset_available() and CANDIDATE_ARTEFACT.is_file()


def football_http_stack_available() -> bool:
    return live_assets_available() and RAW_ARCHIVE.is_dir() and any(RAW_ARCHIVE.rglob("*.json"))


requires_pit_dataset = pytest.mark.skipif(not pit_dataset_available(), reason=_SKIP_REASON)
requires_live_assets = pytest.mark.skipif(not live_assets_available(), reason=_SKIP_REASON)
requires_football_http = pytest.mark.skipif(not football_http_stack_available(), reason=_SKIP_REASON)
