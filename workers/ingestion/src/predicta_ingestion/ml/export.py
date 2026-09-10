from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from predicta_ingestion.ml.dataset import MlDataset
from predicta_ingestion.ml.quality import build_quality_report
from predicta_ingestion.pit.store import PointInTimeStore


def write_dataset_artifacts(
    dataset: MlDataset,
    json_path: str | Path,
    store: PointInTimeStore | None = None,
) -> dict[str, str]:
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dataset.to_dict()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    quality_path = path.with_suffix(".quality.json")
    quality_path.write_text(
        json.dumps(build_quality_report(dataset, store=store), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    parquet_path = path.with_suffix(".parquet")
    _write_parquet(dataset, parquet_path)
    return {
        "json": str(path),
        "parquet": str(parquet_path),
        "quality": str(quality_path),
    }


def _write_parquet(dataset: MlDataset, path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for item in dataset.observations:
        row: dict[str, Any] = {
            "match_id": item.match_id,
            "event_at": item.event_at.isoformat(),
            "home_team_id": item.home_team_id,
            "away_team_id": item.away_team_id,
            "target": item.target.value,
            "home_win": item.home_win,
            "draw": item.draw,
            "away_win": item.away_win,
            "competition": item.competition,
            "competition_id": item.competition_id,
            "competition_name": item.competition_name,
            "season": item.season,
            "season_id": item.season_id,
            "provider": item.provider,
            "raw_payload_id": item.raw_payload_id,
            "data_mode": item.data_mode.value,
            "dataset_version": item.dataset_version,
            "cutoff_policy": item.cutoff_policy,
        }
        row.update(item.features)
        rows.append(row)
    table = pa.Table.from_pylist(rows) if rows else pa.table({})
    pq.write_table(table, path)
