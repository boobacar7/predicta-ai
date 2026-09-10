from datetime import UTC, datetime, timedelta

from predicta_ingestion.canonical.enums import DataMode, MatchStatus, SportCode
from predicta_ingestion.canonical.models import League, Match, Provenance, Sport, Team
from predicta_ingestion.errors import DataLeakageError
from predicta_ingestion.ids import stable_entity_id
from predicta_ingestion.ml.dataset import DATASET_VERSION, build_ml_dataset
from predicta_ingestion.ml.elo import INITIAL_ELO, reconstruct_pre_match_elo
from predicta_ingestion.ml.features import prior_matches_for_features
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
) -> Match:
    sport_id = stable_entity_id("sport", SportCode.FOOTBALL.value)
    league_id = stable_entity_id("league", "football", "mls", "2024")
    if sport_id not in sink.sports:
        sink.sports[sport_id] = Sport(
            id=sport_id,
            code=SportCode.FOOTBALL,
            name="Football",
            provenance=_provenance(provider_id="1", event_at=kickoff, available_at=kickoff),
        )
    if league_id not in sink.leagues:
        sink.leagues[league_id] = League(
            id=league_id,
            sport_id=sport_id,
            name="Major League Soccer",
            country="USA",
            season="2024",
            provenance=_provenance(provider_id="779", event_at=kickoff, available_at=kickoff),
        )
    for team_id, name in ((home, home), (away, away)):
        if team_id not in sink.teams:
            sink.teams[team_id] = Team(
                id=team_id,
                sport_id=sport_id,
                league_id=league_id,
                name=name,
                short_name=name,
                abbreviation=name[:3].upper(),
                provenance=_provenance(provider_id=name, event_at=kickoff, available_at=kickoff),
            )
    match = Match(
        id=match_id,
        sport_id=sport_id,
        league_id=league_id,
        kickoff_at=kickoff,
        status=MatchStatus.FINISHED,
        home_team_id=home,
        away_team_id=away,
        home_score=home_score,
        away_score=away_score,
        provenance=_provenance(provider_id=match_id, event_at=kickoff, available_at=kickoff + available_after),
    )
    sink.matches[match_id] = match
    return match


def test_form_features_exclude_same_day_and_later_matches() -> None:
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
    assert same_day.id not in prior_ids
    assert later.id not in prior_ids
    assert target.id not in prior_ids
    assert features["home_goals_for"] == 2
    assert features["home_goals_for"] != 6
    assert features["home_matches_played"] == 1
    assert by_id[target.id].target is Football1X2Target.HOME
    assert "target" not in features
    assert dataset.dataset_version == DATASET_VERSION
    assert dataset.standings_available is False


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
    assert features["home_goals_for"] == 0
    assert features["home_matches_played"] == 0
    assert leaked.id not in prior_matches_for_features(store, target)
    try:
        store.features_for_match(target.id, datetime(2024, 9, 21, tzinfo=UTC))
    except DataLeakageError:
        pass
    else:
        raise AssertionError("cutoff after kickoff must be rejected")


def test_pre_match_elo_uses_only_preceding_results() -> None:
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
    assert by_id[first.id].features["home_elo_pre"] == INITIAL_ELO
