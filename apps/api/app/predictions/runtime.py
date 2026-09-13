from __future__ import annotations

import sys
from pathlib import Path


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def ensure_ml_on_path() -> Path:
    """Make ``predicta_ml`` importable without republishing the candidate package."""

    src = repository_root() / "workers" / "ml" / "src"
    location = str(src)
    if location not in sys.path:
        sys.path.insert(0, location)
    return src


def ensure_ingestion_on_path() -> Path:
    """Make ``predicta_ingestion`` importable for historical matching. No network."""

    src = repository_root() / "workers" / "ingestion" / "src"
    location = str(src)
    if location not in sys.path:
        sys.path.insert(0, location)
    return src
