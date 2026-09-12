from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from tests.the_odds_api_support import TEST_ODDS_API_KEY, OddsScriptedTransport

from predicta_ingestion.canonical.enums import DataMode, MatchStatus
from predicta_ingestion.canonical.models import Match, Provenance
from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import DataLeakageError, ValidationError
from predicta_ingestion.historical_odds import VALUE_SNAPSHOT_RULE, football_natural_key
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.persist_historical_odds import (
    EXPECTED_WINDOW_MATCH_COUNT,
    INVERTED_PSG_RENNES_MATCH_ID,
    ISOLATED_PARIS_MATCH_ID,
    MAX_PERSIST_REQUESTS,
    MIN_SLOT_GAP,
    PersistSlot,
    PilotMatch,
    TargetMatchOddsSink,
    assert_persist_scope,
    assert_strict_weekend_window,
    plan_persist_slots,
    run_persist_historical_odds_pilot,
    target_match_ids,
)
from predicta_ingestion.persistence.memory import MemoryCanonicalSink, TeeCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.http import RecordedSleep
from predicta_ingestion.providers.the_odds_api import TheOddsApiProvider
from predicta_ingestion.raw.store import FilesystemRawStore

HELIX_ID = "mth_football-sportmonks-helix-persist"
BOURNEMOUTH_ID = "mth_football-sportmonks-bournemouth-persist"
MARSEILLE_ID = "mth_football-sportmonks-marseille-persist"
LYON_ID = "mth_football-sportmonks-lyon-out-of-window"
PARIS_ID = ISOLATED_PARIS_MATCH_ID
RENNES_PSG_ID = INVERTED_PSG_RENNES_MATCH_ID
HELIX_KICKOFF = datetime(2026, 8, 21, 19, tzinfo=UTC)
MARSEILLE_KICKOFF = datetime(2026, 8, 22, 18, 45, tzinfo=UTC)


def _provider(clock: Clock, transport: OddsScriptedTransport) -> TheOddsApiProvider:
    return TheOddsApiProvider(
        enable_live=True,
        api_key=TEST_ODDS_API_KEY,
        clock=clock,
        transport=transport,
        sleeper=RecordedSleep(),
        max_retries=2,
        timeout_seconds=5,
    )


def _pipeline(clock: Clock, live_settings: Settings, tmp_path, match_ids: frozenset[str]) -> IngestionPipeline:
    memory = MemoryCanonicalSink()
    sink = TargetMatchOddsSink(TeeCanonicalSink(memory, None), match_ids)
    return IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=sink,
        resolver=IdentityResolver(clock),
        dry_run=False,
    )


def _matches() -> tuple[PilotMatch, ...]:
    return (
        PilotMatch(
            match_id=HELIX_ID,
            home_team="Helix FC",
            away_team="Meridian Athletic",
            home_team_id="tm_helix",
            away_team_id="tm_meridian",
            league="Premier League",
            league_slug="premier-league",
            kickoff_at=HELIX_KICKOFF,
        ),
        PilotMatch(
            match_id=BOURNEMOUTH_ID,
            home_team="AFC Bournemouth",
            away_team="Brentford",
            home_team_id="tm_football-sportmonks-52",
            away_team_id="tm_brentford",
            league="Premier League",
            league_slug="premier-league",
            kickoff_at=HELIX_KICKOFF,
        ),
        PilotMatch(
            match_id=MARSEILLE_ID,
            home_team="Olympique Marseille",
            away_team="Monaco",
            home_team_id="tm_football-sportmonks-44",
            away_team_id="tm_monaco",
            league="Ligue 1",
            league_slug="ligue-1",
            kickoff_at=MARSEILLE_KICKOFF,
        ),
        PilotMatch(
            match_id=PARIS_ID,
            home_team="Troyes",
            away_team="Paris",
            home_team_id="tm_troyes",
            away_team_id="tm_paris",
            league="Ligue 1",
            league_slug="ligue-1",
            kickoff_at=MARSEILLE_KICKOFF,
        ),
        PilotMatch(
            match_id=RENNES_PSG_ID,
            home_team="Rennes",
            away_team="Paris Saint Germain",
            home_team_id="tm_rennes",
            away_team_id="tm_psg",
            league="Ligue 1",
            league_slug="ligue-1",
            kickoff_at=datetime(2026, 8, 23, 18, 45, tzinfo=UTC),
        ),
    )


def _bind_matches(pipeline: IngestionPipeline) -> None:
    resolver = pipeline._resolver
    resolver.bind_match_natural_key(
        football_natural_key("Helix FC", "Meridian Athletic", HELIX_KICKOFF),
        HELIX_ID,
    )
    resolver.bind_match_natural_key(
        "football|afc-bournemouth|brentford|2026-08-21T19:00:00+00:00",
        BOURNEMOUTH_ID,
    )
    resolver.bind_match_natural_key(
        "football|olympique-marseille|monaco|2026-08-22T18:45:00+00:00",
        MARSEILLE_ID,
    )
    resolver.bind_match_natural_key(
        football_natural_key("Troyes", "Paris", MARSEILLE_KICKOFF),
        PARIS_ID,
    )
    resolver.bind_match_natural_key(
        football_natural_key("Rennes", "Paris Saint Germain", datetime(2026, 8, 23, 18, 45, tzinfo=UTC)),
        RENNES_PSG_ID,
    )
    resolver.bind_match_natural_key(
        football_natural_key("Lyon", "Nice", datetime(2026, 8, 30, 18, 45, tzinfo=UTC)),
        LYON_ID,
    )


def _run(clock: Clock, live_settings: Settings, tmp_path, transport: OddsScriptedTransport | None = None):
    matches = _matches()
    pipeline = _pipeline(clock, live_settings, tmp_path, target_match_ids(matches))
    _bind_matches(pipeline)
    report = run_persist_historical_odds_pilot(
        provider=_provider(clock, transport or OddsScriptedTransport()),
        pipeline=pipeline,
        matches=matches,
        strict_window=False,
        secret=TEST_ODDS_API_KEY,
    )
    return report, pipeline


def test_persist_scope_rejects_backfill_and_dense_cadence() -> None:
    with pytest.raises(ValidationError, match="refuses more than"):
        assert_persist_scope((), max_requests=MAX_PERSIST_REQUESTS + 1)
    with pytest.raises(ValidationError, match="premier-league and ligue-1"):
        assert_persist_scope(
            (PersistSlot(league="la-liga", as_of=HELIX_KICKOFF, kickoff_date="2026-08-21"),),
            max_requests=8,
        )
    close = (
        PersistSlot(league="premier-league", as_of=HELIX_KICKOFF, kickoff_date="2026-08-21"),
        PersistSlot(
            league="premier-league",
            as_of=HELIX_KICKOFF + timedelta(hours=4),
            kickoff_date="2026-08-21",
        ),
    )
    with pytest.raises(ValidationError, match="sub-daily"):
        assert_persist_scope(close, max_requests=8)
    assert MIN_SLOT_GAP >= timedelta(hours=12)


def test_strict_window_refuses_to_guess_a_partial_universe() -> None:
    with pytest.raises(ValidationError, match="Refusing to guess"):
        assert_strict_weekend_window(_matches())
    assert EXPECTED_WINDOW_MATCH_COUNT == 19


def test_plan_slots_is_one_per_league_per_day() -> None:
    slots = plan_persist_slots(_matches())
    assert {(item.league, item.kickoff_date) for item in slots} == {
        ("premier-league", "2026-08-21"),
        ("ligue-1", "2026-08-22"),
        ("ligue-1", "2026-08-23"),
    }
    epl = next(item for item in slots if item.league == "premier-league")
    assert epl.as_of == HELIX_KICKOFF


def test_persist_run_matches_quarantines_and_skips_out_of_scope(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    report, pipeline = _run(clock, live_settings, tmp_path)
    assert report.dry_run is False
    assert report.requests == 3
    assert report.credits_consumed == 30
    assert report.stop_reason is None
    assert TEST_ODDS_API_KEY not in json.dumps(report.to_dict())
    assert report.identity.matched == 3
    assert report.identity.rejected == 3
    assert report.identity.false_match_count == 0
    assert report.identity.exact_matches == 1
    assert report.identity.alias_matches == 2
    assert "fl1_troyes_paris_fc_20260822" in report.identity.rejected_event_ids
    assert "fl1_psg_rennes_inverted_20260823" in report.identity.rejected_event_ids
    assert "epl_unknown_borough_20260821" in report.identity.rejected_event_ids
    assert LYON_ID in report.skipped_out_of_scope
    snapshots = list(pipeline._sink.memory.odds.values())
    match_ids = {item.match_id for item in snapshots}
    assert match_ids == {HELIX_ID, BOURNEMOUTH_ID, MARSEILLE_ID}
    assert pipeline._sink.memory.matches == {}
    assert all(item.provenance.raw_payload_id for item in snapshots)
    assert all(item.provenance.data_mode is DataMode.LIVE for item in snapshots)
    assert all(item.provenance.available_at == item.provenance.collected_at for item in snapshots)
    assert VALUE_SNAPSHOT_RULE in json.dumps(report.to_dict())
    raw_files = list((tmp_path / "raw").rglob("*.json"))
    assert raw_files
    for path in raw_files:
        text = path.read_text(encoding="utf-8")
        assert TEST_ODDS_API_KEY not in text
        assert json.loads(text)["data_mode"] == "live"


def test_persist_is_idempotent_on_identical_payloads(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    matches = _matches()
    pipeline = _pipeline(clock, live_settings, tmp_path, target_match_ids(matches))
    _bind_matches(pipeline)
    first = run_persist_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=pipeline,
        matches=matches,
        strict_window=False,
        secret=TEST_ODDS_API_KEY,
    )
    second = run_persist_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=pipeline,
        matches=matches,
        strict_window=False,
        secret=TEST_ODDS_API_KEY,
    )
    assert first.identity.snapshots == second.identity.snapshots
    assert all(item.get("duplicates", 0) for item in second.ingestion)
    ids = [item.id for item in pipeline._sink.memory.odds.values()]
    assert len(ids) == len(set(ids))


def test_pit_selects_pre_kickoff_and_rejects_post_kickoff(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    report, pipeline = _run(clock, live_settings, tmp_path)
    assert report.pit.passed
    store = PointInTimeStore(pipeline._sink.memory)
    selected = store.odds_as_of(HELIX_ID, HELIX_KICKOFF)
    assert selected is not None
    assert selected.provenance.available_at < HELIX_KICKOFF
    leaked = store.odds_as_of(HELIX_ID, datetime(2026, 8, 21, 18, 40, tzinfo=UTC))
    assert leaked is None

    from predicta_ingestion.canonical.models import OddsSelection, OddsSnapshot
    from predicta_ingestion.ids import stable_entity_id

    future = OddsSnapshot(
        id=stable_entity_id("odds", "the_odds_api", "pinnacle", "future", "1X2", "2026-08-21T19:05:00+00:00"),
        match_id=HELIX_ID,
        market="1X2",
        bookmaker="pinnacle",
        selections=[
            OddsSelection(selection="HOME", label="Helix FC", decimal_odds="1.01"),
            OddsSelection(selection="DRAW", label="Draw", decimal_odds="20"),
            OddsSelection(selection="AWAY", label="Meridian Athletic", decimal_odds="30"),
        ],
        provenance=Provenance(
            provider="the_odds_api",
            provider_id="epl_helix_meridian_20260821:pinnacle:1X2:2026-08-21T19:05:00+00:00",
            collected_at=HELIX_KICKOFF + timedelta(minutes=5),
            available_at=HELIX_KICKOFF + timedelta(minutes=5),
            source="the-odds-api-v4",
            data_mode=DataMode.LIVE,
            event_at=HELIX_KICKOFF,
            raw_payload_id="raw_future",
        ),
    )
    pipeline._sink.memory.odds[future.id] = future
    still = store.odds_as_of(HELIX_ID, HELIX_KICKOFF)
    assert still is not None
    assert still.id == selected.id
    assert still.provenance.available_at < HELIX_KICKOFF


def test_anti_leakage_refuses_post_kickoff_features(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    _report, pipeline = _run(clock, live_settings, tmp_path)
    pipeline._sink.memory.matches[HELIX_ID] = Match(
        id=HELIX_ID,
        sport_id="spt_football",
        league_id="lge_premier-league",
        kickoff_at=HELIX_KICKOFF,
        status=MatchStatus.FINISHED,
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_score=2,
        away_score=1,
        provenance=Provenance(
            provider="sportmonks",
            provider_id="helix",
            collected_at=HELIX_KICKOFF,
            available_at=HELIX_KICKOFF,
            event_at=HELIX_KICKOFF,
            source="sportmonks",
            data_mode=DataMode.LIVE,
        ),
    )
    store = PointInTimeStore(pipeline._sink.memory)
    with pytest.raises(DataLeakageError):
        store.features_for_match(HELIX_ID, HELIX_KICKOFF + timedelta(minutes=1))
    features = store.features_for_match(HELIX_ID, HELIX_KICKOFF)
    assert HELIX_ID not in features["prior_matches"]


def test_reproducible_reconstruction(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    first, first_pipeline = _run(clock, live_settings, tmp_path / "a")
    second, second_pipeline = _run(clock, live_settings, tmp_path / "b")
    assert first.identity.to_dict() == second.identity.to_dict()
    assert {item.id for item in first_pipeline._sink.memory.odds.values()} == {
        item.id for item in second_pipeline._sink.memory.odds.values()
    }
    store_a = PointInTimeStore(first_pipeline._sink.memory)
    store_b = PointInTimeStore(second_pipeline._sink.memory)
    assert store_a.odds_as_of(HELIX_ID, HELIX_KICKOFF).id == store_b.odds_as_of(HELIX_ID, HELIX_KICKOFF).id


def test_target_sink_skips_post_kickoff_snapshots() -> None:
    from decimal import Decimal

    from predicta_ingestion.canonical.models import CanonicalBatch, OddsSelection, OddsSnapshot

    memory = MemoryCanonicalSink()
    sink = TargetMatchOddsSink(
        TeeCanonicalSink(memory, None),
        frozenset({HELIX_ID}),
        kickoffs={HELIX_ID: HELIX_KICKOFF},
    )
    post = OddsSnapshot(
        id="odd_post_kickoff",
        match_id=HELIX_ID,
        market="1X2",
        bookmaker="pinnacle",
        selections=[
            OddsSelection(selection="HOME", label="Helix FC", decimal_odds=Decimal("1.80")),
            OddsSelection(selection="DRAW", label="Draw", decimal_odds=Decimal("3.50")),
            OddsSelection(selection="AWAY", label="Meridian Athletic", decimal_odds=Decimal("4.20")),
        ],
        provenance=Provenance(
            provider="the_odds_api",
            provider_id="post",
            collected_at=HELIX_KICKOFF + timedelta(minutes=5),
            available_at=HELIX_KICKOFF + timedelta(minutes=5),
            source="the-odds-api-v4",
            data_mode=DataMode.LIVE,
        ),
    )
    pre = post.model_copy(
        update={
            "id": "odd_pre_kickoff",
            "provenance": post.provenance.model_copy(
                update={
                    "available_at": HELIX_KICKOFF - timedelta(minutes=5),
                    "collected_at": HELIX_KICKOFF - timedelta(minutes=5),
                }
            ),
        }
    )
    sink.persist(CanonicalBatch(odds=[pre, post]))
    assert "odd_pre_kickoff" in memory.odds
    assert "odd_post_kickoff" not in memory.odds
    assert sink.skipped_post_kickoff == ["odd_post_kickoff"]
