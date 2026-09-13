from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from predicta_ml.constants import CLASS_LABELS, DATASET_VERSION
from predicta_ml.features.schema import FEATURE_SCHEMA


def make_toy_frame(rows: int = 36, start: datetime | None = None) -> pd.DataFrame:
    """Deterministic schema-compatible frame for unit tests. Not a sports dataset."""
    origin = start or datetime(2024, 3, 1, tzinfo=UTC)
    records: list[dict[str, object]] = []
    rng = np.random.default_rng(42)
    for index in range(rows):
        kickoff = origin + timedelta(days=index)
        season = "2024/2025" if index < rows // 2 else "2025/2026"
        records.append(_row(index=index, kickoff=kickoff, rng=rng, season=season))
    return pd.DataFrame.from_records(records)


def make_covering_frame() -> pd.DataFrame:
    """Enough dated rows to populate every production temporal window."""
    stamps = []
    cursor = datetime(2024, 3, 1, 15, 0, tzinfo=UTC)
    end = datetime(2026, 9, 8, 15, 0, tzinfo=UTC)
    while cursor < end:
        stamps.append(cursor)
        cursor += timedelta(days=3)
    records = [
        _row(index=index, kickoff=kickoff, rng=np.random.default_rng(index), season=_season(kickoff))
        for index, kickoff in enumerate(stamps)
    ]
    return pd.DataFrame.from_records(records)


def write_frame_parquet(path: Path, frame: pd.DataFrame) -> None:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    pq.write_table(table, path)


def _season(kickoff: datetime) -> str:
    if kickoff.month >= 7:
        return f"{kickoff.year}/{kickoff.year + 1}"
    return f"{kickoff.year - 1}/{kickoff.year}"


def _row(*, index: int, kickoff: datetime, rng: np.random.Generator, season: str) -> dict[str, object]:
    label = CLASS_LABELS[index % 3]
    home_elo = 1500.0 + float((index % 7) * 12)
    away_elo = 1500.0 - float((index % 5) * 10)
    one_hot = {"HOME": (1, 0, 0), "DRAW": (0, 1, 0), "AWAY": (0, 0, 1)}[label]
    record: dict[str, object] = {
        "match_id": f"match_{index:04d}",
        "event_at": kickoff.isoformat(),
        "home_team_id": f"team_h_{index % 8}",
        "away_team_id": f"team_a_{(index + 3) % 8}",
        "target": label,
        "home_win": one_hot[0],
        "draw": one_hot[1],
        "away_win": one_hot[2],
        "competition": "Test League",
        "competition_id": "test-league",
        "competition_name": "Test League",
        "season": season,
        "season_id": "s1",
        "provider": "sportmonks",
        "raw_payload_id": f"raw_{index}",
        "data_mode": "live",
        "dataset_version": DATASET_VERSION,
        "cutoff_policy": "pre_kickoff",
        "home_elo_pre": home_elo,
        "away_elo_pre": away_elo,
        "elo_diff": home_elo - away_elo,
        "elo_available": 1,
        "home_form_5": int(rng.integers(0, 13)),
        "away_form_5": int(rng.integers(0, 13)),
        "home_form_10": int(rng.integers(0, 25)),
        "away_form_10": int(rng.integers(0, 25)),
        "home_form_5_available": 1 if index > 4 else 0,
        "away_form_5_available": 1 if index > 4 else 0,
        "home_form_10_available": 1 if index > 9 else 0,
        "away_form_10_available": 1 if index > 9 else 0,
        "home_goals_for_5": int(rng.integers(0, 12)),
        "home_goals_against_5": int(rng.integers(0, 12)),
        "home_goals_for_10": int(rng.integers(0, 20)),
        "home_goals_against_10": int(rng.integers(0, 20)),
        "away_goals_for_5": int(rng.integers(0, 12)),
        "away_goals_against_5": int(rng.integers(0, 12)),
        "away_goals_for_10": int(rng.integers(0, 20)),
        "away_goals_against_10": int(rng.integers(0, 20)),
        "h2h_home_wins": int(index % 3),
        "h2h_draws": int(index % 2),
        "h2h_away_wins": int((index + 1) % 3),
        "h2h_available": 1 if index > 6 else 0,
        "h2h_matches": min(index, 4),
        "home_matches_played": index,
        "away_matches_played": max(index - 1, 0),
    }
    missing = [name for name in FEATURE_SCHEMA if name not in record]
    if missing:
        raise AssertionError(f"Toy row missing features: {missing}")
    return record
