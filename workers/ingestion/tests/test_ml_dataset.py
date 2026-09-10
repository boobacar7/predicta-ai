from datetime import UTC, datetime, timedelta
from pathlib import Path

from predicta_ingestion.canonical.enums import DataMode, MatchStatus, SportCode
from predicta_ingestion.canonical.models import League, Match, Provenance, Sport, Team
from predicta_ingestion.errors import DataLeakageError
from predicta_ingestion.ids import stable_entity_id
from predicta_ingestion.ml.dataset import DATASET_VERSION, build_ml_dataset
from predicta_ingestion.ml.elo import INITIAL_ELO, reconstruct_pre_match_elo
from predicta_ingestion.ml.export import write_dataset_artifacts
from predicta_ingestion.ml.features import FEATURE_SCHEMA, FEATURE_SCHEMA_VERSION, prior_matches_for_features
from predicta_ingestion.ml.quality import build_quality_report
from predicta_ingestion.ml.targets import Football1X2Target
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pit.store import PointInTimeStore


def _provenance(*, provider_id: str, event_at: datetime, available_at: datetime) -> Provenance:
    return Provenance(
        provider="sportmonks",
        provider_id=provider_id,
        collected_at=datetime(2026, 1, 1, tzinfo=UTC),
        available_at=available_at,
        event_at=event_at,
        source="sportmonks",
        data_mode=DataMode.LIVE,
        raw_payload_id=f"raw_{provider_id}",
    )


def _seed_match(
    sink: MemoryCanonicalSink,
    *,
    match_id: str,
    kickoff: datetime,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    available_after: timedelta = timedelta(hours=3),
    status: MatchStatus = MatchStatus.FINISHED,
    league_id: str | None = None,
    league_name: str = "Major League Soccer",
    competition_id: str = "mls",
    season: str = "2024",
    country: str = "USA",
    provider_league_id: str = "779",
    provider_season_id: str = "18001",
) -> Match:
    sport_id = stable_entity_id("sport", SportCode.FOOTBALL.value)
    resolved_league_id = league_id or stable_entity_id("league", "football", "mls", "2024")
    if sport_id not in sink.sports:
        sink.sports[sport_id] = Sport(
            id=sport_id,
            code=SportCode.FOOTBALL,
            name="Football",
            provenance=_provenance(provider_id="1", event_at=kickoff, available_at=kickoff),
        )
    if resolved_league_id not in sink.leagues:
        sink.leagues[resolved_league_id] = League(
            id=resolved_league_id,
            sport_id=sport_id,
            name=league_name,
            country=country,
            season=season,
            competition_id=competition_id,
            provider_season_id=provider_season_id,
            provenance=_provenance(provider_id=provider_league_id, event_at=kickoff, available_at=kickoff),
        )
    for team_id, name in ((home, home), (away, away)):
        if team_id not in sink.teams:
            sink.teams[team_id] = Team(
                id=team_id,
                sport_id=sport_id,
                league_id=resolved_league_id,
                name=name,
                short_name=name,
                abbreviation=name[:3].upper(),
                provenance=_provenance(provider_id=name, event_at=kickoff, available_at=kickoff),
            )
    match = Match(
        id=match_id,
        sport_id=sport_id,
        league_id=resolved_league_id,
        kickoff_at=kickoff,
        status=status,
        home_team_id=home,
        away_team_id=away,
        home_score=home_score if status is MatchStatus.FINISHED else None,
        away_score=away_score if status is MatchStatus.FINISHED else None,
        provenance=_provenance(provider_id=match_id, event_at=kickoff, available_at=kickoff + available_after),
    )
    sink.matches[match_id] = match
    return match


def test_form_features_use_earlier_same_day_only_when_available() -> None:
    sink = MemoryCanonicalSink()
    prior = _seed_match(
        sink,
        match_id="m_prior",
        kickoff=datetime(2024, 9, 13, 20, 0, tzinfo=UTC),
        home="psg",
        away="lens",
        home_score=2,
        away_score=0,
    )
    same_day = _seed_match(
        sink,
        match_id="m_same_day",
        kickoff=datetime(2024, 9, 20, 12, 0, tzinfo=UTC),
        home="psg",
        away="nantes",
        home_score=4,
        away_score=0,
    )
    target = _seed_match(
        sink,
        match_id="m_target",
        kickoff=datetime(2024, 9, 20, 20, 0, tzinfo=UTC),
        home="psg",
        away="marseille",
        home_score=1,
        away_score=0,
    )
    later = _seed_match(
        sink,
        match_id="m_later",
        kickoff=datetime(2024, 9, 21, 20, 0, tzinfo=UTC),
        home="psg",
        away="lyon",
        home_score=5,
        away_score=0,
    )
    store = PointInTimeStore(sink)
    dataset = build_ml_dataset(store, competition="mls", seasons=["2024"])
    by_id = {item.match_id: item for item in dataset.observations}
    features = by_id[target.id].features
    prior_ids = {item.id for item in prior_matches_for_features(store, target)}
    assert prior.id in prior_ids
    assert same_day.id in prior_ids
    assert later.id not in prior_ids
    assert target.id not in prior_ids
    assert features["home_goals_for_5"] == 6
    assert features["home_matches_played"] == 2
    assert by_id[target.id].target is Football1X2Target.HOME
    assert by_id[target.id].home_win == 1
    assert by_id[target.id].draw == 0
    assert by_id[target.id].away_win == 0
    assert "target" not in features
    assert dataset.dataset_version == DATASET_VERSION
    assert dataset.standings_available is False
    assert list(features) == list(FEATURE_SCHEMA)


def test_post_kickoff_fact_cannot_enter_features() -> None:
    sink = MemoryCanonicalSink()
    target = _seed_match(
        sink,
        match_id="m_target",
        kickoff=datetime(2024, 9, 20, 20, 0, tzinfo=UTC),
        home="home",
        away="away",
        home_score=1,
        away_score=0,
    )
    leaked = _seed_match(
        sink,
        match_id="m_leaked",
        kickoff=datetime(2024, 9, 19, 20, 0, tzinfo=UTC),
        home="home",
        away="other",
        home_score=7,
        away_score=0,
        available_after=timedelta(days=3),
    )
    store = PointInTimeStore(sink)
    dataset = build_ml_dataset(store, competition="mls")
    features = next(item.features for item in dataset.observations if item.match_id == target.id)
    assert features["home_goals_for_5"] == 0
    assert features["home_matches_played"] == 0
    assert leaked.id not in prior_matches_for_features(store, target)
    try:
        store.features_for_match(target.id, datetime(2024, 9, 21, tzinfo=UTC))
    except DataLeakageError:
        pass
    else:
        raise AssertionError("cutoff after kickoff must be rejected")


def test_pre_match_elo_uses_only_preceding_available_results() -> None:
    sink = MemoryCanonicalSink()
    first = _seed_match(
        sink,
        match_id="elo_1",
        kickoff=datetime(2024, 8, 1, 20, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=1,
        away_score=0,
    )
    second = _seed_match(
        sink,
        match_id="elo_2",
        kickoff=datetime(2024, 8, 8, 20, 0, tzinfo=UTC),
        home="alpha",
        away="gamma",
        home_score=0,
        away_score=1,
    )
    pre = reconstruct_pre_match_elo(list(sink.matches.values()))
    assert pre[first.id] == (INITIAL_ELO, INITIAL_ELO)
    assert pre[second.id][0] > INITIAL_ELO
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="mls")
    by_id = {item.match_id: item for item in dataset.observations}
    assert by_id[first.id].features["home_elo_pre"] == INITIAL_ELO
    assert by_id[second.id].features["home_elo_pre"] != by_id[second.id].features["away_elo_pre"]
    assert by_id[second.id].features["elo_diff"] == (
        by_id[second.id].features["home_elo_pre"] - by_id[second.id].features["away_elo_pre"]
    )


def test_elo_does_not_apply_until_available_at() -> None:
    sink = MemoryCanonicalSink()
    early = _seed_match(
        sink,
        match_id="elo_early",
        kickoff=datetime(2024, 8, 1, 12, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=1,
        away_score=0,
        available_after=timedelta(hours=3),
    )
    overlap = _seed_match(
        sink,
        match_id="elo_overlap",
        kickoff=datetime(2024, 8, 1, 13, 0, tzinfo=UTC),
        home="alpha",
        away="gamma",
        home_score=1,
        away_score=0,
        available_after=timedelta(hours=3),
    )
    pre = reconstruct_pre_match_elo(list(sink.matches.values()))
    assert pre[early.id] == (INITIAL_ELO, INITIAL_ELO)
    assert pre[overlap.id] == (INITIAL_ELO, INITIAL_ELO)


def test_rolling_windows_five_and_ten() -> None:
    sink = MemoryCanonicalSink()
    start = datetime(2024, 3, 1, 20, 0, tzinfo=UTC)
    for index in range(12):
        _seed_match(
            sink,
            match_id=f"roll_{index}",
            kickoff=start + timedelta(days=index * 7),
            home="home",
            away=f"opp_{index}",
            home_score=1 if index < 10 else 3,
            away_score=0,
        )
    target = _seed_match(
        sink,
        match_id="roll_target",
        kickoff=start + timedelta(days=12 * 7),
        home="home",
        away="final",
        home_score=1,
        away_score=0,
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="mls")
    features = next(item.features for item in dataset.observations if item.match_id == target.id)
    assert features["home_matches_played"] == 12
    assert features["home_form_5_available"] == 1
    assert features["home_form_10_available"] == 1
    assert features["home_form_5"] == 15
    assert features["home_goals_for_5"] == 9
    assert features["home_goals_for_10"] == 14
    assert features["home_form_10"] == 30


def test_h2h_requires_prior_meetings() -> None:
    sink = MemoryCanonicalSink()
    first = _seed_match(
        sink,
        match_id="h2h_1",
        kickoff=datetime(2024, 4, 1, 20, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=2,
        away_score=0,
    )
    second = _seed_match(
        sink,
        match_id="h2h_2",
        kickoff=datetime(2024, 5, 1, 20, 0, tzinfo=UTC),
        home="beta",
        away="alpha",
        home_score=1,
        away_score=1,
    )
    target = _seed_match(
        sink,
        match_id="h2h_3",
        kickoff=datetime(2024, 6, 1, 20, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=0,
        away_score=1,
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="mls")
    by_id = {item.match_id: item for item in dataset.observations}
    assert by_id[first.id].features["h2h_available"] == 0
    assert by_id[second.id].features["h2h_matches"] == 1
    assert by_id[target.id].features["h2h_available"] == 1
    assert by_id[target.id].features["h2h_matches"] == 2
    assert by_id[target.id].features["h2h_home_wins"] == 1
    assert by_id[target.id].features["h2h_draws"] == 1
    assert by_id[target.id].home_win == 0
    assert by_id[target.id].away_win == 1


def test_unfinished_matches_are_rejected_not_labeled() -> None:
    sink = MemoryCanonicalSink()
    _seed_match(
        sink,
        match_id="finished",
        kickoff=datetime(2024, 8, 1, 20, 0, tzinfo=UTC),
        home="a",
        away="b",
        home_score=1,
        away_score=0,
    )
    _seed_match(
        sink,
        match_id="future",
        kickoff=datetime(2026, 10, 1, 20, 0, tzinfo=UTC),
        home="a",
        away="c",
        home_score=0,
        away_score=0,
        status=MatchStatus.SCHEDULED,
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="mls")
    assert dataset.observation_count == 1
    assert dataset.rejected_count == 1
    assert dataset.rejections[0].reason == "not_finished"


def test_dataset_export_and_quality_report(tmp_path: Path) -> None:
    sink = MemoryCanonicalSink()
    _seed_match(
        sink,
        match_id="exp_1",
        kickoff=datetime(2024, 8, 1, 20, 0, tzinfo=UTC),
        home="a",
        away="b",
        home_score=1,
        away_score=0,
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="mls")
    paths = write_dataset_artifacts(dataset, tmp_path / "mls-1x2.json")
    quality = build_quality_report(dataset)
    assert Path(paths["json"]).is_file()
    assert Path(paths["parquet"]).is_file()
    assert Path(paths["quality"]).is_file()
    assert quality["observation_count"] == 1
    assert quality["anti_leakage"]["violations"] == 0
    assert quality["temporal_order_ok"] is True
    assert quality["duplicate_match_ids"] == []
    assert quality["feature_count"] == len(FEATURE_SCHEMA)


def test_elo_is_global_across_competitions() -> None:
    sink = MemoryCanonicalSink()
    ucl_kickoff = datetime(2024, 9, 1, 19, 0, tzinfo=UTC)
    league_kickoff = datetime(2024, 9, 8, 19, 0, tzinfo=UTC)
    sport_id = stable_entity_id("sport", SportCode.FOOTBALL.value)
    ucl_league_id = stable_entity_id("league", "football", "ucl", "2024/2025")
    sink.sports[sport_id] = Sport(
        id=sport_id,
        code=SportCode.FOOTBALL,
        name="Football",
        provenance=_provenance(provider_id="1", event_at=ucl_kickoff, available_at=ucl_kickoff),
    )
    sink.leagues[ucl_league_id] = League(
        id=ucl_league_id,
        sport_id=sport_id,
        name="UEFA Champions League",
        country="Europe",
        season="2024/2025",
        competition_id="champions-league",
        provider_season_id="23619",
        provenance=_provenance(provider_id="2:2024/2025", event_at=ucl_kickoff, available_at=ucl_kickoff),
    )
    europe = Match(
        id="ucl_prior",
        sport_id=sport_id,
        league_id=ucl_league_id,
        kickoff_at=ucl_kickoff,
        status=MatchStatus.FINISHED,
        home_team_id="psg",
        away_team_id="bayern",
        home_score=2,
        away_score=0,
        provenance=_provenance(
            provider_id="ucl_prior",
            event_at=ucl_kickoff,
            available_at=ucl_kickoff + timedelta(hours=3),
        ),
    )
    sink.matches[europe.id] = europe
    domestic = _seed_match(
        sink,
        match_id="ligue1_after",
        kickoff=league_kickoff,
        home="psg",
        away="lens",
        home_score=1,
        away_score=0,
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="all")
    labeled = next(item for item in dataset.observations if item.match_id == domestic.id)
    assert labeled.features["home_elo_pre"] != INITIAL_ELO
    assert labeled.home_team_id == "psg"
    assert labeled.competition_id == "mls"
    assert labeled.competition_name == "Major League Soccer"
    assert labeled.season == "2024"
    ucl = next(item for item in dataset.observations if item.match_id == europe.id)
    assert ucl.home_team_id == labeled.home_team_id
    assert ucl.competition_id == "champions-league"


def test_elo_has_no_leakage_from_target_or_later_results() -> None:
    sink = MemoryCanonicalSink()
    first = _seed_match(
        sink,
        match_id="elo_first",
        kickoff=datetime(2024, 8, 1, 20, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=1,
        away_score=0,
    )
    later = _seed_match(
        sink,
        match_id="elo_later",
        kickoff=datetime(2024, 8, 15, 20, 0, tzinfo=UTC),
        home="alpha",
        away="gamma",
        home_score=4,
        away_score=0,
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="all")
    by_id = {item.match_id: item for item in dataset.observations}
    assert by_id[first.id].features["home_elo_pre"] == INITIAL_ELO
    assert by_id[first.id].features["away_elo_pre"] == INITIAL_ELO
    assert by_id[later.id].features["home_elo_pre"] != INITIAL_ELO
    assert by_id[first.id].features["home_elo_pre"] != by_id[later.id].features["home_elo_pre"]


def test_rolling_windows_exclude_target_and_future_matches() -> None:
    sink = MemoryCanonicalSink()
    prior = _seed_match(
        sink,
        match_id="roll_prior",
        kickoff=datetime(2024, 9, 1, 20, 0, tzinfo=UTC),
        home="home",
        away="opp_a",
        home_score=2,
        away_score=0,
    )
    target = _seed_match(
        sink,
        match_id="roll_target",
        kickoff=datetime(2024, 9, 8, 20, 0, tzinfo=UTC),
        home="home",
        away="opp_b",
        home_score=7,
        away_score=0,
    )
    future = _seed_match(
        sink,
        match_id="roll_future",
        kickoff=datetime(2024, 9, 15, 20, 0, tzinfo=UTC),
        home="home",
        away="opp_c",
        home_score=9,
        away_score=0,
    )
    store = PointInTimeStore(sink)
    dataset = build_ml_dataset(store, competition="all")
    features = next(item.features for item in dataset.observations if item.match_id == target.id)
    prior_ids = {item.id for item in prior_matches_for_features(store, target)}
    assert prior.id in prior_ids
    assert target.id not in prior_ids
    assert future.id not in prior_ids
    assert features["home_goals_for_5"] == 2
    assert features["home_form_5"] == 3


def test_h2h_uses_only_prior_kickoffs() -> None:
    sink = MemoryCanonicalSink()
    prior = _seed_match(
        sink,
        match_id="h2h_prior",
        kickoff=datetime(2024, 4, 1, 20, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=2,
        away_score=0,
    )
    target = _seed_match(
        sink,
        match_id="h2h_target",
        kickoff=datetime(2024, 5, 1, 20, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=5,
        away_score=0,
    )
    later = _seed_match(
        sink,
        match_id="h2h_future",
        kickoff=datetime(2024, 6, 1, 20, 0, tzinfo=UTC),
        home="beta",
        away="alpha",
        home_score=0,
        away_score=4,
    )
    store = PointInTimeStore(sink)
    dataset = build_ml_dataset(store, competition="all")
    by_id = {item.match_id: item for item in dataset.observations}
    assert by_id[target.id].features["h2h_matches"] == 1
    assert by_id[target.id].features["h2h_home_wins"] == 1
    assert by_id[target.id].features["h2h_available"] == 0
    prior_ids = {item.id for item in prior_matches_for_features(store, target)}
    assert prior.id in prior_ids
    assert later.id not in prior_ids
    assert target.id not in prior_ids


def test_available_at_equal_to_kickoff_is_excluded() -> None:
    sink = MemoryCanonicalSink()
    delayed = _seed_match(
        sink,
        match_id="avail_delayed",
        kickoff=datetime(2024, 8, 1, 12, 0, tzinfo=UTC),
        home="alpha",
        away="beta",
        home_score=3,
        away_score=0,
        available_after=timedelta(hours=8),
    )
    target = _seed_match(
        sink,
        match_id="avail_target",
        kickoff=datetime(2024, 8, 1, 20, 0, tzinfo=UTC),
        home="alpha",
        away="gamma",
        home_score=1,
        away_score=0,
    )
    store = PointInTimeStore(sink)
    dataset = build_ml_dataset(store, competition="all")
    features = next(item.features for item in dataset.observations if item.match_id == target.id)
    assert delayed.provenance.available_at == target.kickoff_at
    assert delayed.id not in {item.id for item in prior_matches_for_features(store, target)}
    assert features["home_matches_played"] == 0
    assert features["home_elo_pre"] == INITIAL_ELO


def test_identical_timestamps_snapshot_before_update() -> None:
    sink = MemoryCanonicalSink()
    kickoff = datetime(2024, 8, 1, 15, 0, tzinfo=UTC)
    first = _seed_match(
        sink,
        match_id="tie_a",
        kickoff=kickoff,
        home="alpha",
        away="beta",
        home_score=1,
        away_score=0,
        available_after=timedelta(0),
    )
    second = _seed_match(
        sink,
        match_id="tie_b",
        kickoff=kickoff,
        home="gamma",
        away="delta",
        home_score=2,
        away_score=0,
        available_after=timedelta(0),
    )
    later = _seed_match(
        sink,
        match_id="tie_c",
        kickoff=kickoff + timedelta(hours=3),
        home="alpha",
        away="gamma",
        home_score=1,
        away_score=0,
        available_after=timedelta(hours=3),
    )
    pre = reconstruct_pre_match_elo(list(sink.matches.values()))
    assert pre[first.id] == (INITIAL_ELO, INITIAL_ELO)
    assert pre[second.id] == (INITIAL_ELO, INITIAL_ELO)
    assert pre[later.id][0] != INITIAL_ELO
    assert pre[later.id][1] != INITIAL_ELO
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="all")
    by_id = {item.match_id: item for item in dataset.observations}
    assert by_id[first.id].features["home_elo_pre"] == INITIAL_ELO
    assert by_id[second.id].features["home_elo_pre"] == INITIAL_ELO


def test_team_present_in_multiple_competitions() -> None:
    sink = MemoryCanonicalSink()
    ucl_league_id = stable_entity_id("league", "football", "champions-league", "2024/2025")
    ligue1_league_id = stable_entity_id("league", "football", "ligue-1", "2024/2025")
    europe = _seed_match(
        sink,
        match_id="ucl_psg",
        kickoff=datetime(2024, 9, 1, 19, 0, tzinfo=UTC),
        home="tm_football-sportmonks-591",
        away="tm_football-sportmonks-504",
        home_score=2,
        away_score=0,
        league_id=ucl_league_id,
        league_name="Champions League",
        competition_id="champions-league",
        season="2024/2025",
        country="Europe",
        provider_league_id="2",
        provider_season_id="23619",
    )
    domestic = _seed_match(
        sink,
        match_id="l1_psg",
        kickoff=datetime(2024, 9, 8, 19, 0, tzinfo=UTC),
        home="tm_football-sportmonks-591",
        away="tm_football-sportmonks-44",
        home_score=1,
        away_score=0,
        league_id=ligue1_league_id,
        league_name="Ligue 1",
        competition_id="ligue-1",
        season="2024/2025",
        country="France",
        provider_league_id="301",
        provider_season_id="23614",
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="all")
    by_id = {item.match_id: item for item in dataset.observations}
    assert by_id[europe.id].home_team_id == by_id[domestic.id].home_team_id
    assert by_id[europe.id].competition_id == "champions-league"
    assert by_id[domestic.id].competition_id == "ligue-1"
    assert by_id[domestic.id].features["home_matches_played"] == 1
    assert by_id[domestic.id].features["home_elo_pre"] != INITIAL_ELO
    assert set(dataset.competitions) == {"champions-league", "ligue-1"}


def test_canonical_team_id_is_global_across_competitions() -> None:
    sink = MemoryCanonicalSink()
    ucl_league_id = stable_entity_id("league", "football", "champions-league", "2024/2025")
    ligue1_league_id = stable_entity_id("league", "football", "ligue-1", "2024/2025")
    canonical = "tm_football-sportmonks-591"
    _seed_match(
        sink,
        match_id="ucl_id",
        kickoff=datetime(2024, 10, 1, 19, 0, tzinfo=UTC),
        home=canonical,
        away="tm_football-sportmonks-85",
        home_score=1,
        away_score=0,
        league_id=ucl_league_id,
        league_name="Champions League",
        competition_id="champions-league",
        season="2024/2025",
        country="Europe",
        provider_league_id="2",
        provider_season_id="23619",
    )
    _seed_match(
        sink,
        match_id="l1_id",
        kickoff=datetime(2024, 10, 5, 19, 0, tzinfo=UTC),
        home=canonical,
        away="tm_football-sportmonks-18",
        home_score=0,
        away_score=0,
        league_id=ligue1_league_id,
        league_name="Ligue 1",
        competition_id="ligue-1",
        season="2024/2025",
        country="France",
        provider_league_id="301",
        provider_season_id="23614",
    )
    dataset = build_ml_dataset(PointInTimeStore(sink), competition="all")
    ids = {item.home_team_id for item in dataset.observations}
    assert ids == {canonical}
    assert {item.competition_id for item in dataset.observations} == {"champions-league", "ligue-1"}


def test_future_match_is_excluded_from_labeled_rows() -> None:
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
    assert dataset.rejected_count == 1
    assert dataset.rejections[0].reason == "not_finished"
    assert dataset.rejections[0].match_id == "scheduled_future"


def test_dataset_is_reproducible() -> None:
    sink = MemoryCanonicalSink()
    _seed_match(
        sink,
        match_id="rep_1",
        kickoff=datetime(2024, 8, 1, 20, 0, tzinfo=UTC),
        home="a",
        away="b",
        home_score=1,
        away_score=0,
    )
    _seed_match(
        sink,
        match_id="rep_2",
        kickoff=datetime(2024, 8, 8, 20, 0, tzinfo=UTC),
        home="a",
        away="c",
        home_score=0,
        away_score=1,
    )
    generated_at = datetime(2026, 9, 10, 16, 0, tzinfo=UTC)
    store = PointInTimeStore(sink)
    first = build_ml_dataset(store, competition="all", generated_at=generated_at)
    second = build_ml_dataset(store, competition="all", generated_at=generated_at)
    assert first.to_dict() == second.to_dict()
    assert first.observation_count == 2
    assert first.feature_schema_version == FEATURE_SCHEMA_VERSION
    quality = build_quality_report(first, store=store)
    assert quality["anti_leakage"]["violations"] == 0
    assert quality["anti_leakage"]["point_in_time"]["ok"] is True
