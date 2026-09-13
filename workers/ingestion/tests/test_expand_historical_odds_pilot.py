from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from tests.the_odds_api_support import TEST_ODDS_API_KEY, OddsScriptedTransport

from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.expand_historical_odds import (
    EXPAND_WINDOWS,
    ISOLATED_PARIS_TEAM_ID,
    MAX_EXPAND_REQUESTS,
    ExpandWindow,
    estimate_expand_run,
    isolated_paris_match_ids,
    partition_slots,
    run_expand_historical_odds_pilot,
)
from predicta_ingestion.historical_odds import CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED, football_natural_key
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.persist_historical_odds import (
    MAX_PERSIST_REQUESTS,
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
from predicta_ingestion.providers.http import RecordedSleep
from predicta_ingestion.providers.the_odds_api import TheOddsApiProvider
from predicta_ingestion.raw.store import FilesystemRawStore

HELIX_ID = "mth_football-sportmonks-helix-expand"
MARSEILLE_ID = "mth_football-sportmonks-marseille-expand"
PARIS_ID = "mth_football-sportmonks-19715629"
MAY_KICKOFF = datetime(2026, 5, 2, 15, 0, tzinfo=UTC)
WEEKEND_KICKOFF = datetime(2026, 8, 21, 19, tzinfo=UTC)
FOLLOWING_KICKOFF = datetime(2026, 8, 29, 14, 0, tzinfo=UTC)


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
            match_id="mth_may_helix",
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=MAY_KICKOFF,
        ),
        _match(
            match_id=HELIX_ID,
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=WEEKEND_KICKOFF,
        ),
        _match(
            match_id="mth_follow_helix",
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=FOLLOWING_KICKOFF,
        ),
        _match(
            match_id=PARIS_ID,
            home="Troyes",
            away="Paris",
            home_id="tm_troyes",
            away_id=ISOLATED_PARIS_TEAM_ID,
            league="Ligue 1",
            slug="ligue-1",
            kickoff=datetime(2026, 8, 22, 18, 45, tzinfo=UTC),
        ),
        _match(
            match_id="mth_may_paris",
            home="Paris",
            away="Brest",
            home_id=ISOLATED_PARIS_TEAM_ID,
            away_id="tm_brest",
            league="Ligue 1",
            slug="ligue-1",
            kickoff=datetime(2026, 5, 3, 15, 15, tzinfo=UTC),
        ),
    )


def test_expand_windows_are_pl_l1_and_skip_the_persisted_weekend() -> None:
    assert {item.name for item in EXPAND_WINDOWS} == {
        "end-2025-26-may",
        "persist-weekend-2026-08-21",
        "2026-27-following-matchweeks",
    }
    reuse = next(item for item in EXPAND_WINDOWS if not item.fetch)
    assert reuse.start.isoformat() == "2026-08-21T00:00:00+00:00"
    assert reuse.end.isoformat() == "2026-08-25T00:00:00+00:00"
    assert all(item.fetch or item is reuse for item in EXPAND_WINDOWS)
    assert MAX_EXPAND_REQUESTS > MAX_PERSIST_REQUESTS
    assert MAX_EXPAND_REQUESTS * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED == 400
    assert MIN_SLOT_GAP >= timedelta(hours=12)


def test_estimate_skips_reuse_weekend_and_already_persisted_slots() -> None:
    matches = _universe()
    estimate = estimate_expand_run(
        matches=matches,
        persisted_ids=frozenset({"mth_follow_helix"}),
    )
    fetch_dates = {(item.league, item.kickoff_date) for item in estimate.fetch_slots}
    skipped = {(item.league, item.kickoff_date) for item in estimate.skipped_already_persisted}
    assert ("premier-league", "2026-08-21") not in fetch_dates
    assert ("premier-league", "2026-08-21") not in skipped
    assert ("premier-league", "2026-08-29") in skipped
    assert ("premier-league", "2026-05-02") in fetch_dates
    assert ("ligue-1", "2026-05-03") in fetch_dates
    assert estimate.estimated_credits == len(estimate.fetch_slots) * 10
    assert estimate.stop_reason is None
    assert TEST_ODDS_API_KEY not in json.dumps(estimate.to_dict())


def test_expand_cap_stops_instead_of_silent_backfill(
    monkeypatch: pytest.MonkeyPatch, clock: Clock, live_settings: Settings, tmp_path
) -> None:
    monkeypatch.setattr("predicta_ingestion.expand_historical_odds.MAX_EXPAND_REQUESTS", 1)
    estimate = estimate_expand_run(matches=_universe(), persisted_ids=frozenset())
    assert estimate.stop_reason is not None
    assert "MAX_EXPAND_REQUESTS" in estimate.stop_reason
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=TargetMatchOddsSink(TeeCanonicalSink(MemoryCanonicalSink(), None), frozenset()),
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    with pytest.raises(ValidationError, match="MAX_EXPAND_REQUESTS"):
        run_expand_historical_odds_pilot(
            provider=TheOddsApiProvider(
                enable_live=False,
                api_key="",
                clock=clock,
            ),
            pipeline=pipeline,
            estimate=estimate,
            estimate_only=False,
        )


def test_expand_scope_rejects_other_leagues() -> None:
    with pytest.raises(ValidationError, match="premier-league and ligue-1"):
        estimate_expand_run(
            matches=(
                _match(
                    match_id="mth_liga",
                    home="A",
                    away="B",
                    home_id="tm_a",
                    away_id="tm_b",
                    league="La Liga",
                    slug="la-liga",
                    kickoff=MAY_KICKOFF,
                ),
            ),
            persisted_ids=frozenset(),
        )
    with pytest.raises(ValidationError, match="refuses more than"):
        assert_persist_scope((), max_requests=MAX_EXPAND_REQUESTS + 1, request_cap=MAX_EXPAND_REQUESTS)


def test_isolated_paris_matches_stay_distinct() -> None:
    ids = isolated_paris_match_ids(_universe())
    assert PARIS_ID in ids
    assert "mth_may_paris" in ids
    assert HELIX_ID not in ids


def test_partition_does_not_refetch_complete_league_days() -> None:
    matches = _universe()
    slots = plan_persist_slots(matches)
    fetch, skipped = partition_slots(slots, matches, frozenset({HELIX_ID}))
    weekend = PersistSlot(league="premier-league", as_of=WEEKEND_KICKOFF, kickoff_date="2026-08-21")
    assert weekend in skipped
    assert weekend not in fetch


def test_expand_reuses_persist_runner_without_creating_matches(
    clock: Clock, live_settings: Settings, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "predicta_ingestion.expand_historical_odds.EXPAND_WINDOWS",
        (
            ExpandWindow(
                name="scripted-fetch",
                start=datetime(2026, 8, 21, tzinfo=UTC),
                end=datetime(2026, 8, 25, tzinfo=UTC),
                fetch=True,
            ),
        ),
    )
    matches = (
        _match(
            match_id=HELIX_ID,
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=WEEKEND_KICKOFF,
        ),
        _match(
            match_id=MARSEILLE_ID,
            home="Olympique Marseille",
            away="Monaco",
            home_id="tm_football-sportmonks-44",
            away_id="tm_monaco",
            league="Ligue 1",
            slug="ligue-1",
            kickoff=datetime(2026, 8, 22, 18, 45, tzinfo=UTC),
        ),
    )
    estimate = estimate_expand_run(matches=matches, persisted_ids=frozenset())
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
        football_natural_key("Helix FC", "Meridian Athletic", WEEKEND_KICKOFF),
        HELIX_ID,
    )
    pipeline._resolver.bind_match_natural_key(
        "football|olympique-marseille|monaco|2026-08-22T18:45:00+00:00",
        MARSEILLE_ID,
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
    report = run_expand_historical_odds_pilot(
        provider=provider,
        pipeline=pipeline,
        estimate=estimate,
        secret=TEST_ODDS_API_KEY,
        estimate_only=False,
    )
    assert report.estimate_only is False
    assert report.dry_run is False
    assert report.persist is not None
    assert report.persist.requests == len(estimate.fetch_slots)
    assert TEST_ODDS_API_KEY not in json.dumps(report.to_dict())
    assert pipeline._sink.memory.matches == {}
    persisted = {item.match_id for item in pipeline._sink.memory.odds.values()}
    assert persisted <= {HELIX_ID, MARSEILLE_ID}


def test_estimate_only_does_not_fetch(clock: Clock, live_settings: Settings, tmp_path) -> None:
    estimate = estimate_expand_run(matches=_universe(), persisted_ids=frozenset())
    transport = OddsScriptedTransport()
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=TargetMatchOddsSink(TeeCanonicalSink(MemoryCanonicalSink(), None), frozenset()),
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    report = run_expand_historical_odds_pilot(
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
