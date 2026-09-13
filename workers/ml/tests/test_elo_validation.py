from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from predicta_ml.constants import ELO_HA_GRID, ELO_K_GRID
from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.models.elo import elo_1x2_probabilities
from predicta_ml.models.elo_walk import reconstruct_pre_match_elo
from tests.support import make_covering_frame, make_toy_frame, write_frame_parquet


def test_reconstructed_elo_does_not_use_future_results(tmp_path: Path) -> None:
    path = tmp_path / "toy.parquet"
    write_frame_parquet(path, make_toy_frame(12, start=datetime(2024, 3, 1, tzinfo=UTC)))
    dataset = load_football_dataset(path)
    original = reconstruct_pre_match_elo(dataset.frame, k=20, home_advantage=80)
    mutated = dataset.frame.copy()
    mutated.loc[mutated.index[-1], "y"] = int((int(mutated.loc[mutated.index[-1], "y"]) + 1) % 3)
    rebuilt = reconstruct_pre_match_elo(mutated, k=20, home_advantage=80)
    assert np.allclose(
        original.iloc[:-1]["reconstructed_elo_diff"].to_numpy(),
        rebuilt.iloc[:-1]["reconstructed_elo_diff"].to_numpy(),
    )
    assert float(original.iloc[0]["reconstructed_home_elo"]) == 1500.0
    assert float(original.iloc[0]["reconstructed_away_elo"]) == 1500.0


def test_same_kickoff_snapshots_do_not_see_each_other() -> None:
    origin = datetime(2024, 8, 1, 15, 0, tzinfo=UTC)
    frame = make_toy_frame(2, start=origin)
    stamp = origin.isoformat()
    frame["event_at"] = stamp
    rebuilt = reconstruct_pre_match_elo(frame, k=20, home_advantage=80)
    assert float(rebuilt.iloc[0]["reconstructed_home_elo"]) == 1500.0
    assert float(rebuilt.iloc[1]["reconstructed_home_elo"]) == 1500.0


def test_later_update_can_change_a_later_snapshot() -> None:
    origin = datetime(2024, 8, 1, tzinfo=UTC)
    frame = make_toy_frame(2, start=origin)
    frame.loc[0, "event_at"] = origin.isoformat()
    frame.loc[1, "event_at"] = (origin + timedelta(days=7)).isoformat()
    frame.loc[0, "home_team_id"] = "same_home"
    frame.loc[1, "home_team_id"] = "same_home"
    frame.loc[0, "away_team_id"] = "opp_a"
    frame.loc[1, "away_team_id"] = "opp_b"
    frame.loc[0, "target"] = "HOME"
    rebuilt = reconstruct_pre_match_elo(frame, k=20, home_advantage=80)
    assert float(rebuilt.iloc[1]["reconstructed_home_elo"]) > 1500.0


def test_draw_probability_is_never_dropped() -> None:
    diffs = np.linspace(-400.0, 400.0, 81)
    proba = elo_1x2_probabilities(diffs, home_advantage=80.0, scale=400.0, draw_base=0.277, draw_decay=1.11)
    assert proba.shape[1] == 3
    assert np.all(proba[:, 1] > 0.0)
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert int((proba.argmax(axis=1) == 1).sum()) == 0


def test_sensitivity_grid_is_the_documented_25_cells() -> None:
    assert ELO_K_GRID == (10, 15, 20, 25, 30)
    assert ELO_HA_GRID == (0, 40, 60, 80, 100)
    assert len(ELO_K_GRID) * len(ELO_HA_GRID) == 25


def test_candidate_is_not_production() -> None:
    from predicta_ml.constants import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS

    assert CANDIDATE_MODEL_VERSION == "football-elo-v1-candidate"
    assert CANDIDATE_STATUS == "candidate"


def test_covering_frame_loads_for_validation_helpers(tmp_path: Path) -> None:
    path = tmp_path / "cover.parquet"
    write_frame_parquet(path, make_covering_frame())
    dataset = load_football_dataset(path)
    rebuilt = reconstruct_pre_match_elo(dataset.frame, k=10, home_advantage=0)
    assert len(rebuilt) == len(dataset.frame)
    assert not rebuilt.isna().to_numpy().any()
