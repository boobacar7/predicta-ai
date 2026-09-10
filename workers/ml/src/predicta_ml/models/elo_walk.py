from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from predicta_ml.constants import (
    CLASS_INDEX,
    ELO_HOME_ADVANTAGE,
    ELO_INITIAL,
    ELO_K,
    ELO_SCALE,
    ELO_UPDATE_DELAY_HOURS,
)


def reconstruct_pre_match_elo(
    frame: pd.DataFrame,
    *,
    k: float = ELO_K,
    home_advantage: float = ELO_HOME_ADVANTAGE,
    initial: float = ELO_INITIAL,
    scale: float = ELO_SCALE,
    update_delay_hours: int = ELO_UPDATE_DELAY_HOURS,
) -> pd.DataFrame:
    """Causal Elo walk from dataset 1X2 labels only.

    Snapshot at ``event_at``. Update at ``event_at + 3h`` (the dataset parquet
    does not store ``available_at``; this matches the Data-layer hypothesis).
    Events sort by ``(timestamp, kind, match_id)`` with snapshot kind=0 before
    update kind=1. The target match never updates its own pre-match ratings.
    """
    delay = timedelta(hours=update_delay_hours)
    home_ids = frame["home_team_id"].to_numpy()
    away_ids = frame["away_team_id"].to_numpy()
    match_ids = frame["match_id"].astype(str).to_numpy()
    if "y" in frame.columns:
        labels = frame["y"].to_numpy(dtype=np.int64)
    else:
        labels = frame["target"].map(CLASS_INDEX).to_numpy(dtype=np.int64)
    events: list[tuple[pd.Timestamp, int, str, int]] = []
    for row_index, timestamp in enumerate(frame["event_at"]):
        kickoff = pd.Timestamp(timestamp)
        events.append((kickoff, 0, match_ids[row_index], row_index))
        events.append((kickoff + delay, 1, match_ids[row_index], row_index))
    events.sort(key=lambda item: (item[0], item[1], item[2]))
    ratings: dict[str, float] = {}
    home_pre = np.empty(len(frame), dtype=np.float64)
    away_pre = np.empty(len(frame), dtype=np.float64)
    for _when, kind, _match_id, row_index in events:
        home_id = str(home_ids[row_index])
        away_id = str(away_ids[row_index])
        home_rating = ratings.get(home_id, initial)
        away_rating = ratings.get(away_id, initial)
        if kind == 0:
            home_pre[row_index] = home_rating
            away_pre[row_index] = away_rating
            continue
        expected_home = 1.0 / (1.0 + 10 ** ((away_rating - (home_rating + home_advantage)) / scale))
        outcome = int(labels[row_index])
        if outcome == CLASS_INDEX["HOME"]:
            home_actual, away_actual = 1.0, 0.0
        elif outcome == CLASS_INDEX["AWAY"]:
            home_actual, away_actual = 0.0, 1.0
        else:
            home_actual, away_actual = 0.5, 0.5
        ratings[home_id] = home_rating + k * (home_actual - expected_home)
        ratings[away_id] = away_rating + k * (away_actual - (1.0 - expected_home))
    return pd.DataFrame(
        {
            "reconstructed_home_elo": home_pre,
            "reconstructed_away_elo": away_pre,
            "reconstructed_elo_diff": home_pre - away_pre,
        },
        index=frame.index,
    )
