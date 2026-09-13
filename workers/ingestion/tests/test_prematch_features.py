from datetime import UTC, datetime, timedelta

import pytest
from tests.test_ml_dataset import _seed_match

from predicta_ingestion.canonical.enums import MatchStatus
from predicta_ingestion.errors import DataLeakageError
from predicta_ingestion.ml.dataset import DATASET_VERSION, build_ml_dataset
from predicta_ingestion.ml.elo import ELO_K, HOME_ADVANTAGE, reconstruct_pre_match_elo, snapshot_pre_match_elo
from predicta_ingestion.ml.features import FEATURE_SCHEMA_VERSION, prior_matches_for_features
from predicta_ingestion.ml.prematch import PREMATCH_FEATURE_ORIGIN, build_prematch_features, write_prematch_artifacts
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pit.store import PointInTimeStore


def test_candidate_elo_parameters_are_unchanged() -> None:
    assert ELO_K == 20.0
    assert HOME_ADVANTAGE == 80.0


def test_labeled_dataset_still_rejects_scheduled_matches() -> None:
    sink = MemoryCanonicalSink()
    finished = _seed_match(
        sink,
        match_id="labeled",
        kickoff=datetime(2024, 8, 1, 20, 0, tzinfo=UTC),
        home="a",
        away="b",
        home_score=1,
        away_score=0,
    )
    _seed_match(
        sink,
        match_id="scheduled_future",
        kickoff=datetime(2026, 10, 1, 20, 0, tzinfo=UTC),
        home="a",
        away="c",
        home_score=0,
        away_score=0,
        status=MatchStatus.SCHEDULED,
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="all")
    assert [item.match_id for item in dataset.observations] == [finished.id]
    assert dataset.rejections[0].reason == "not_finished"


def test_scheduled_prematch_features_use_only_prior_finished_results() -> None:
    sink = MemoryCanonicalSink()
    prior = _seed_match(
        sink,
        match_id="prior_home",
        kickoff=datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
        home="liverpool",
        away="bournemouth",
        home_score=2,
        away_score=0,
    )
    opponent = _seed_match(
        sink,
        match_id="prior_away",
        kickoff=datetime(2026, 8, 8, 15, 0, tzinfo=UTC),
        home="everton",
        away="fulham",
        home_score=3,
        away_score=0,
    )
    future = _seed_match(
        sink,
        match_id="future_finished",
        kickoff=datetime(2026, 9, 20, 15, 0, tzinfo=UTC),
        home="liverpool",
        away="arsenal",
        home_score=5,
        away_score=0,
    )
    scheduled = _seed_match(
        sink,
        match_id="mth_football-sportmonks-19722167",
        kickoff=datetime(2026, 9, 12, 14, 0, tzinfo=UTC),
        home="liverpool",
        away="fulham",
        home_score=0,
        away_score=0,
        status=MatchStatus.SCHEDULED,
    )
    store = PointInTimeStore(sink)
    features = build_prematch_features(store)
    assert features.dataset_version == DATASET_VERSION
    assert features.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert features.feature_origin == PREMATCH_FEATURE_ORIGIN
    assert features.observation_count == 1
    row = features.observations[0]
    assert row.match_id == scheduled.id
    assert "target" not in row.features
    prior_ids = {item.id for item in prior_matches_for_features(store, scheduled)}
    assert prior.id in prior_ids
    assert opponent.id in prior_ids
    assert future.id not in prior_ids
    assert scheduled.id not in prior_ids
    assert row.features["home_matches_played"] == 1
    assert row.features["away_matches_played"] == 1
    assert row.features["home_goals_for_5"] == 2
    assert row.features["elo_available"] == 1
    assert row.features["home_elo_pre"] != row.features["away_elo_pre"]


def test_prematch_cutoff_excludes_post_cutoff_results() -> None:
    sink = MemoryCanonicalSink()
    leaked = _seed_match(
        sink,
        match_id="leaked",
        kickoff=datetime(2026, 9, 11, 14, 0, tzinfo=UTC),
        home="liverpool",
        away="chelsea",
        home_score=7,
        away_score=0,
        available_after=timedelta(days=3),
    )
    scheduled = _seed_match(
        sink,
        match_id="scheduled",
        kickoff=datetime(2026, 9, 12, 14, 0, tzinfo=UTC),
        home="liverpool",
        away="fulham",
        home_score=0,
        away_score=0,
        status=MatchStatus.SCHEDULED,
    )
    store = PointInTimeStore(sink)
    row = build_prematch_features(store).observations[0]
    assert leaked.id not in {item.id for item in prior_matches_for_features(store, scheduled)}
    assert row.features["home_goals_for_5"] == 0
    assert row.features["home_matches_played"] == 0


def test_post_kickoff_cutoff_is_rejected_for_scheduled_match() -> None:
    sink = MemoryCanonicalSink()
    scheduled = _seed_match(
        sink,
        match_id="scheduled",
        kickoff=datetime(2026, 9, 12, 14, 0, tzinfo=UTC),
        home="liverpool",
        away="fulham",
        home_score=0,
        away_score=0,
        status=MatchStatus.SCHEDULED,
    )
    store = PointInTimeStore(sink)
    with pytest.raises(DataLeakageError, match="at or before kickoff"):
        store.assert_pre_kickoff(scheduled, scheduled.kickoff_at + timedelta(microseconds=1))


def test_snapshot_elo_does_not_use_scheduled_score_and_matches_finished_walk() -> None:
    sink = MemoryCanonicalSink()
    finished = _seed_match(
        sink,
        match_id="finished",
        kickoff=datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
        home="liverpool",
        away="fulham",
        home_score=2,
        away_score=0,
    )
    scheduled = _seed_match(
        sink,
        match_id="scheduled",
        kickoff=datetime(2026, 9, 12, 14, 0, tzinfo=UTC),
        home="liverpool",
        away="fulham",
        home_score=0,
        away_score=0,
        status=MatchStatus.SCHEDULED,
    )
    finished_only = reconstruct_pre_match_elo([finished])
    combined = snapshot_pre_match_elo([finished, scheduled])
    assert combined[finished.id] == finished_only[finished.id]
    home_after, away_after = combined[scheduled.id]
    assert (home_after, away_after) != finished_only[finished.id]
    assert scheduled.id not in finished_only


def test_prematch_parquet_has_no_labels(tmp_path) -> None:
    sink = MemoryCanonicalSink()
    _seed_match(
        sink,
        match_id="scheduled",
        kickoff=datetime(2026, 9, 12, 14, 0, tzinfo=UTC),
        home="liverpool",
        away="fulham",
        home_score=0,
        away_score=0,
        status=MatchStatus.SCHEDULED,
    )
    features = build_prematch_features(PointInTimeStore(sink))
    paths = write_prematch_artifacts(features, tmp_path / "prematch.json")
    import pyarrow.parquet as pq

    table = pq.read_table(paths["parquet"])
    names = set(table.column_names)
    assert "target" not in names
    assert "home_win" not in names
    assert table.column("feature_origin")[0].as_py() == PREMATCH_FEATURE_ORIGIN
    assert table.column("match_id")[0].as_py() == "scheduled"
