from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from tests.the_odds_api_support import TEST_ODDS_API_KEY, OddsScriptedTransport

from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.expand_historical_odds import ISOLATED_PARIS_TEAM_ID
from predicta_ingestion.historical_odds import CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED, football_natural_key
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.oos_historical_odds import (
    EXPECTED_OOS_MATCH_COUNT,
    MAX_OOS_REQUESTS,
    OOS_END,
    OOS_LEAGUES,
    OOS_START,
    MatchOddsState,
    OosOddsExpansionReport,
    build_coverage_matrix,
    estimate_oos_odds_run,
    existing_historical_request_keys,
    historical_request_key,
    isolated_oos_match_ids,
    load_oos_match_ids_from_parquet,
    run_expand_oos_historical_odds,
    write_oos_odds_artefacts,
)
from predicta_ingestion.persist_historical_odds import (
    MIN_SLOT_GAP,
    PersistSlot,
    PilotMatch,
    TargetMatchOddsSink,
    assert_persist_scope,
    plan_persist_slots,
    target_match_ids,
)
from predicta_ingestion.persistence.memory import MemoryCanonicalSink, TeeCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.http import RecordedSleep
from predicta_ingestion.providers.the_odds_api import TheOddsApiProvider
from predicta_ingestion.raw.store import FilesystemRawStore

HELIX_ID = "mth_football-sportmonks-helix-oos"
LIGA_ID = "mth_football-sportmonks-liga-oos"
PARIS_ID = "mth_football-sportmonks-19715629"
MLS_ID = "mth_football-sportmonks-mls-oos"
HELIX_KICKOFF = datetime(2026, 8, 21, 19, 0, tzinfo=UTC)
LIGA_KICKOFF = datetime(2026, 8, 21, 19, 0, tzinfo=UTC)
MLS_KICKOFF = datetime(2026, 8, 15, 23, 30, tzinfo=UTC)
PARIS_KICKOFF = datetime(2026, 8, 22, 18, 45, tzinfo=UTC)


def _match(
    *,
    match_id: str,
    home: str,
    away: str,
    home_id: str,
    away_id: str,
    league: str,
    slug: str,
    kickoff: datetime,
) -> PilotMatch:
    return PilotMatch(
        match_id=match_id,
        home_team=home,
        away_team=away,
        home_team_id=home_id,
        away_team_id=away_id,
        league=league,
        league_slug=slug,
        kickoff_at=kickoff,
    )


def _universe() -> tuple[PilotMatch, ...]:
    return (
        _match(
            match_id=HELIX_ID,
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=HELIX_KICKOFF,
        ),
        _match(
            match_id=LIGA_ID,
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="La Liga",
            slug="la-liga",
            kickoff=LIGA_KICKOFF,
        ),
        _match(
            match_id=MLS_ID,
            home="Inter Miami",
            away="Atlanta United",
            home_id="tm_miami",
            away_id="tm_atlanta",
            league="Major League Soccer",
            slug="mls",
            kickoff=MLS_KICKOFF,
        ),
        _match(
            match_id=PARIS_ID,
            home="Troyes",
            away="Paris",
            home_id="tm_troyes",
            away_id=ISOLATED_PARIS_TEAM_ID,
            league="Ligue 1",
            slug="ligue-1",
            kickoff=PARIS_KICKOFF,
        ),
    )


def test_oos_window_and_leagues_are_frozen() -> None:
    assert OOS_START.isoformat() == "2026-07-01T00:00:00+00:00"
    assert OOS_END.isoformat() == "2026-09-10T02:30:01+00:00"
    assert OOS_LEAGUES == (
        "mls",
        "premier-league",
        "la-liga",
        "bundesliga",
        "serie-a",
        "ligue-1",
        "champions-league",
    )
    assert MAX_OOS_REQUESTS * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED == 850
    assert MIN_SLOT_GAP >= timedelta(hours=12)
    assert EXPECTED_OOS_MATCH_COUNT == 387


def test_estimate_skips_covered_requested_and_isolated_paris() -> None:
    matches = _universe()
    existing = frozenset({historical_request_key("mls", MLS_KICKOFF)})
    estimate = estimate_oos_odds_run(
        matches=matches,
        covered_ids=frozenset({HELIX_ID}),
        existing_request_keys=existing,
    )
    fetch = {(item.league, item.kickoff_date) for item in estimate.fetch_slots}
    assert ("premier-league", "2026-08-21") not in fetch
    assert ("mls", "2026-08-15") not in fetch
    assert ("ligue-1", "2026-08-22") not in fetch
    assert ("la-liga", "2026-08-21") in fetch
    assert PARIS_ID in estimate.isolated_match_ids
    assert estimate.estimated_credits == 10
    assert estimate.stop_reason is None
    assert estimate.plan_sha256
    assert TEST_ODDS_API_KEY not in json.dumps(estimate.to_dict())


def test_estimate_refuses_matches_outside_oos_window() -> None:
    with pytest.raises(ValidationError, match="outside the OOS window"):
        estimate_oos_odds_run(
            matches=(
                _match(
                    match_id="mth_may",
                    home="A",
                    away="B",
                    home_id="tm_a",
                    away_id="tm_b",
                    league="La Liga",
                    slug="la-liga",
                    kickoff=datetime(2026, 5, 2, 15, 0, tzinfo=UTC),
                ),
            ),
            covered_ids=frozenset(),
            existing_request_keys=frozenset(),
        )
    with pytest.raises(ValidationError, match="outside the OOS window"):
        estimate_oos_odds_run(
            matches=(
                _match(
                    match_id="mth_2024",
                    home="A",
                    away="B",
                    home_id="tm_a",
                    away_id="tm_b",
                    league="Premier League",
                    slug="premier-league",
                    kickoff=datetime(2024, 8, 16, 19, 0, tzinfo=UTC),
                ),
            ),
            covered_ids=frozenset(),
            existing_request_keys=frozenset(),
        )


def test_oos_cap_stops_instead_of_silent_backfill(
    monkeypatch: pytest.MonkeyPatch, clock: Clock, live_settings: Settings, tmp_path: Path
) -> None:
    monkeypatch.setattr("predicta_ingestion.oos_historical_odds.MAX_OOS_REQUESTS", 1)
    estimate = estimate_oos_odds_run(
        matches=_universe(),
        covered_ids=frozenset(),
        existing_request_keys=frozenset(),
    )
    assert estimate.stop_reason is not None
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=TargetMatchOddsSink(TeeCanonicalSink(MemoryCanonicalSink(), None), frozenset()),
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    with pytest.raises(ValidationError, match="MAX_OOS_REQUESTS"):
        run_expand_oos_historical_odds(
            provider=TheOddsApiProvider(enable_live=False, api_key="", clock=clock),
            pipeline=pipeline,
            estimate=estimate,
            estimate_only=False,
        )


def test_plan_persist_slots_accepts_v1_leagues_for_oos() -> None:
    slots = plan_persist_slots(_universe(), allowed_leagues=OOS_LEAGUES)
    leagues = {item.league for item in slots}
    assert "la-liga" in leagues
    assert "mls" in leagues
    with pytest.raises(ValidationError, match="premier-league and ligue-1"):
        plan_persist_slots(_universe())


def test_isolated_paris_matches_are_not_refetched() -> None:
    ids = isolated_oos_match_ids(_universe())
    assert PARIS_ID in ids
    assert HELIX_ID not in ids


def test_coalesce_keeps_earliest_as_of_across_utc_midnight() -> None:
    from predicta_ingestion.oos_historical_odds import coalesce_slots

    early = PersistSlot(league="mls", as_of=datetime(2026, 7, 16, 23, 30, tzinfo=UTC), kickoff_date="2026-07-16")
    later = PersistSlot(league="mls", as_of=datetime(2026, 7, 17, 0, 30, tzinfo=UTC), kickoff_date="2026-07-17")
    kept, dropped = coalesce_slots((early, later))
    assert kept == (early,)
    assert dropped == (later,)


def test_existing_request_keys_are_read_from_raw_envelopes(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "live" / "the_odds_api" / "2026" / "08" / "21"
    raw.mkdir(parents=True)
    key = historical_request_key("la-liga", LIGA_KICKOFF)
    (raw / "raw_the-odds-api-odds-deadbeef.json").write_text(
        json.dumps({"request_key": key, "provider": "the_odds_api", "data_mode": "live"}),
        encoding="utf-8",
    )
    assert key in existing_historical_request_keys(tmp_path / "raw")


def test_parquet_loader_requires_exact_oos_count(tmp_path: Path) -> None:
    path = tmp_path / "too-small.parquet"
    table = pa.table(
        {
            "match_id": ["mth_1"],
            "event_at": [datetime(2026, 8, 21, 19, tzinfo=UTC)],
            "dataset_version": ["football-1x2-history-0.3"],
            "data_mode": ["live"],
        }
    )
    pq.write_table(table, path)
    with pytest.raises(ValidationError, match="Expected 387"):
        load_oos_match_ids_from_parquet(path)

    ids = [f"mth_{index}" for index in range(EXPECTED_OOS_MATCH_COUNT)]
    kickoffs = [datetime(2026, 8, 21, 19, tzinfo=UTC)] * EXPECTED_OOS_MATCH_COUNT
    full = pa.table(
        {
            "match_id": ids,
            "event_at": kickoffs,
            "dataset_version": ["football-1x2-history-0.3"] * EXPECTED_OOS_MATCH_COUNT,
            "data_mode": ["live"] * EXPECTED_OOS_MATCH_COUNT,
        }
    )
    full_path = tmp_path / "full.parquet"
    pq.write_table(full, full_path)
    loaded = load_oos_match_ids_from_parquet(full_path)
    assert len(loaded) == EXPECTED_OOS_MATCH_COUNT
    assert loaded[0] == "mth_0"


def test_estimate_only_does_not_fetch(clock: Clock, live_settings: Settings, tmp_path: Path) -> None:
    estimate = estimate_oos_odds_run(
        matches=_universe(),
        covered_ids=frozenset({HELIX_ID}),
        existing_request_keys=frozenset(),
    )
    transport = OddsScriptedTransport()
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=TargetMatchOddsSink(TeeCanonicalSink(MemoryCanonicalSink(), None), frozenset()),
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    report = run_expand_oos_historical_odds(
        provider=TheOddsApiProvider(
            enable_live=True,
            api_key=TEST_ODDS_API_KEY,
            clock=clock,
            transport=transport,
            sleeper=RecordedSleep(),
        ),
        pipeline=pipeline,
        estimate=estimate,
        secret=TEST_ODDS_API_KEY,
        estimate_only=True,
    )
    assert report.estimate_only is True
    assert report.persist is None
    assert transport.calls == []
    assert report.credits_consumed == 0


def test_quota_probe_stops_before_historical_requests(
    clock: Clock, live_settings: Settings, tmp_path: Path
) -> None:
    estimate = estimate_oos_odds_run(
        matches=(_universe()[1],),
        covered_ids=frozenset(),
        existing_request_keys=frozenset(),
    )
    assert estimate.estimated_credits == 10
    transport = OddsScriptedTransport()
    transport.requests_remaining = 5
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=TargetMatchOddsSink(TeeCanonicalSink(MemoryCanonicalSink(), None), target_match_ids(_universe())),
        resolver=IdentityResolver(clock),
        dry_run=False,
    )
    provider = TheOddsApiProvider(
        enable_live=True,
        api_key=TEST_ODDS_API_KEY,
        clock=clock,
        transport=transport,
        sleeper=RecordedSleep(),
        max_retries=2,
        timeout_seconds=5,
    )
    with pytest.raises(ValidationError, match="Remaining Odds API credits"):
        run_expand_oos_historical_odds(
            provider=provider,
            pipeline=pipeline,
            estimate=estimate,
            secret=TEST_ODDS_API_KEY,
            estimate_only=False,
            probe_quota=True,
        )
    assert len(transport.calls) == 1
    assert "/v4/sports" in transport.calls[0][0]
    assert "/historical/" not in transport.calls[0][0]


def test_oos_runner_reuses_persist_and_keeps_pit(
    clock: Clock, live_settings: Settings, tmp_path: Path
) -> None:
    matches = (
        _match(
            match_id=LIGA_ID,
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="La Liga",
            slug="la-liga",
            kickoff=LIGA_KICKOFF,
        ),
    )
    estimate = estimate_oos_odds_run(
        matches=matches,
        covered_ids=frozenset(),
        existing_request_keys=frozenset(),
    )
    memory = MemoryCanonicalSink()
    sink = TargetMatchOddsSink(TeeCanonicalSink(memory, None), target_match_ids(matches))
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=sink,
        resolver=IdentityResolver(clock),
        dry_run=False,
    )
    pipeline._resolver.bind_match_natural_key(
        football_natural_key("Helix FC", "Meridian Athletic", LIGA_KICKOFF),
        LIGA_ID,
    )
    provider = TheOddsApiProvider(
        enable_live=True,
        api_key=TEST_ODDS_API_KEY,
        clock=clock,
        transport=OddsScriptedTransport(),
        sleeper=RecordedSleep(),
        max_retries=2,
        timeout_seconds=5,
    )
    report = run_expand_oos_historical_odds(
        provider=provider,
        pipeline=pipeline,
        estimate=estimate,
        secret=TEST_ODDS_API_KEY,
        estimate_only=False,
        probe_quota=False,
        coverage={},
    )
    assert report.persist is not None
    assert report.persist.requests == 1
    assert report.dry_run is False
    assert pipeline._sink.memory.matches == {}
    snapshots = list(pipeline._sink.memory.odds.values())
    assert snapshots
    assert all(item.provenance.data_mode.value == "live" for item in snapshots)
    assert all(item.match_id == LIGA_ID for item in snapshots)
    assert all(item.provenance.available_at <= LIGA_KICKOFF for item in snapshots)
    store = PointInTimeStore(pipeline._sink.memory)
    selected = store.odds_as_of(LIGA_ID, LIGA_KICKOFF)
    assert selected is not None
    assert selected.provenance.available_at <= LIGA_KICKOFF
    assert TEST_ODDS_API_KEY not in json.dumps(report.to_dict())
    reused = estimate_oos_odds_run(
        matches=matches,
        covered_ids=frozenset({LIGA_ID}),
        existing_request_keys=existing_historical_request_keys(tmp_path / "raw"),
    )
    assert reused.fetch_slots == ()
    assert {item.id for item in pipeline._sink.memory.odds.values()} == {item.id for item in snapshots}


def test_coverage_matrix_distinguishes_existing_from_new() -> None:
    matches = _universe()
    states = {
        HELIX_ID: MatchOddsState(HELIX_ID, 3, HELIX_KICKOFF - timedelta(hours=1), HELIX_KICKOFF, 3),
        LIGA_ID: MatchOddsState(LIGA_ID, 0, None, None, 0),
        MLS_ID: MatchOddsState(MLS_ID, 0, None, None, 0),
        PARIS_ID: MatchOddsState(PARIS_ID, 0, None, None, 0),
    }
    coverage = build_coverage_matrix(matches, states, previously_covered=frozenset({HELIX_ID}))
    assert coverage["covered_before"] == 1
    assert coverage["covered_after"] == 1
    by_id = {str(item["match_id"]): item for item in coverage["rows"]}  # type: ignore[index]
    assert by_id[HELIX_ID]["existing_odds"] is True
    assert by_id[HELIX_ID]["valid_pre_match_snapshot"] is True
    assert str(by_id[PARIS_ID]["rejection_reason"]).startswith("isolated_team")
    assert by_id[LIGA_ID]["rejection_reason"] == "no_live_1x2_snapshot"


def test_write_artefacts_redacts_secrets(tmp_path: Path) -> None:
    estimate = estimate_oos_odds_run(
        matches=_universe()[:1],
        covered_ids=frozenset({HELIX_ID}),
        existing_request_keys=frozenset(),
    )
    report = OosOddsExpansionReport(
        estimate=estimate,
        persist=None,
        coverage={"covered_before": 1, "newly_covered": 0},
        dry_run=True,
        estimate_only=True,
        credits_planned=0,
        credits_consumed=0,
    )
    paths = write_oos_odds_artefacts(
        report,
        coverage_path=tmp_path / "coverage.json",
        manifest_path=tmp_path / "manifest.json",
    )
    coverage_text = Path(paths["coverage"]).read_text(encoding="utf-8")
    manifest_text = Path(paths["manifest"]).read_text(encoding="utf-8")
    assert TEST_ODDS_API_KEY not in coverage_text
    assert TEST_ODDS_API_KEY not in manifest_text
    assert "apikey=" not in manifest_text.lower()


def test_assert_persist_scope_oos_cap() -> None:
    with pytest.raises(ValidationError, match="refuses more than"):
        assert_persist_scope((), max_requests=MAX_OOS_REQUESTS + 1, request_cap=MAX_OOS_REQUESTS)
    slot = PersistSlot(league="la-liga", as_of=LIGA_KICKOFF, kickoff_date="2026-08-21")
    assert_persist_scope(
        (slot,),
        max_requests=MAX_OOS_REQUESTS,
        request_cap=MAX_OOS_REQUESTS,
        allowed_leagues=OOS_LEAGUES,
    )
