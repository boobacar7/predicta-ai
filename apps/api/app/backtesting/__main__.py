from __future__ import annotations

import json
import sys

from app.predictions.runtime import ensure_ingestion_on_path, ensure_ml_on_path, repository_root
from app.predictions.types import CANDIDATE_MODEL_VERSION

ensure_ml_on_path()
ensure_ingestion_on_path()

from app.backtesting.pilot import run_fixture_pilot, run_live_weekend_model_pilot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    del argv
    report = run_fixture_pilot()
    payload: dict[str, object] = {"fixture": report, "live_weekend": None}
    dataset = repository_root() / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    registry = repository_root() / "workers" / "ml" / "var" / "registry"
    if dataset.is_file() and (registry / CANDIDATE_MODEL_VERSION / "artefact.joblib").is_file():
        payload["live_weekend"] = run_live_weekend_model_pilot(dataset_path=dataset, registry_dir=registry)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
