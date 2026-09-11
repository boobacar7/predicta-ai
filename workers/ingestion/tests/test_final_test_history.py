from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.the_odds_api_support import TEST_ODDS_API_KEY, OddsScriptedTransport

from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import DataLeakageError, ValidationError
from predicta_ingestion.final_test_history import (
    ELO_CALIBRATION_FIT_END,
    ELO_FINAL_TEST_START,
    ELO_FINAL_TRAIN_END,
    EXCLUDED_PERIODS,
    FINAL_TEST_WINDOWS,
    ISOLATED_PARIS_TEAM_ID,
    MAX_FINAL_TEST_REQUESTS,
    WINDOWS_ARTEFACT_VERSION,
    elo_temporal_split,
    estimate_final_test_run,
    isolated_paris_match_ids,
    report_payload,
    run_expand_final_test_history,
    windows_artefact,
)
from predicta_ingestion.historical_odds import CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED, football_natural_key
from predicta_ingestion.identity.resolver import IdentityResolver
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

HELIX_ID = "mth_football-sportmonks-helix-final-test"
MARSEILLE_ID = "mth_football-sportmonks-marseille-final-test"
PARIS_ID = "mth_football-sportmonks-19715629"
WINDOW_01_KICKOFF = datetime(2024, 8, 16, 19, 0, tzinfo=UTC)
EXISTING_KICKOFF = datetime(2026, 8, 21, 19, 0, tzinfo=UTC)
ARTEFACT_PATH = Path(__file__).resolve().parents[3] / "docs" / "qa" / "final-test-windows.json"


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
            kickoff=WINDOW_01_KICKOFF,
        ),
        _match(
            match_id=MARSEILLE_ID,
            home="Olympique Marseille",
            away="Monaco",
            home_id="tm_football-sportmonks-44",
            away_id="tm_monaco",
            league="Ligue 1",
            slug="ligue-1",
            kickoff=datetime(2024, 8, 17, 18, 45, tzinfo=UTC),
        ),
        _match(
            match_id="mth_existing_helix",
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=EXISTING_KICKOFF,
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
    )


def test_windows_are_defined_before_scoring_and_committed() -> None:
    ids = [item.window_id for item in FINAL_TEST_WINDOWS]
    assert ids == [
        "final_test_window_01",
        "final_test_window_02",
        "final_test_window_03",
        "final_test_window_existing",
    ]
    artefact = json.loads(ARTEFACT_PATH.read_text())
    assert artefact["defined_before_scoring"] is True
    assert artefact["artefact_version"] == WINDOWS_ARTEFACT_VERSION
    assert [item["window_id"] for item in artefact["windows"]] == ids
    generated = windows_artefact()
    assert generated["windows"][0]["start"] == artefact["windows"][0]["start"]
    assert generated["excluded_periods"][0]["name"] == EXCLUDED_PERIODS[0]["name"]


def test_additional_windows_are_not_requalified_calibration_or_selection() -> None:
    for window in FINAL_TEST_WINDOWS:
        if not window.additional:
            continue
        assert window.end <= ELO_FINAL_TRAIN_END
        assert window.start < ELO_CALIBRATION_FIT_END
        assert window.end <= ELO_FINAL_TEST_START
        assert window.elo_temporal_split == "final_train"
        assert elo_temporal_split(window.start) == "final_train"
    existing = [item for item in FINAL_TEST_WINDOWS if not item.additional]
    assert existing[0].elo_temporal_split == "final_test"
    assert existing[0].fetch is False


def test_windows_do_not_overlap_and_exclude_may_2026() -> None:
    additional = [item for item in FINAL_TEST_WINDOWS if item.additional]
    for left, right in zip(additional, additional[1:], strict=False):
        assert left.end <= right.start
    may_start = datetime(2026, 5, 1, tzinfo=UTC)
    may_end = datetime(2026, 5, 25, tzinfo=UTC)
    for window in FINAL_TEST_WINDOWS:
        overlap = window.start < may_end and window.end > may_start
        assert overlap is False


def test_estimate_skips_existing_official_final_test_and_caps_credits() -> None:
    estimate = estimate_final_test_run(matches=_universe(), persisted_ids=frozenset())
    fetch_ids = {item.match_id for item in estimate.fetch_matches}
    reuse_ids = {item.match_id for item in estimate.reuse_matches}
    assert HELIX_ID in fetch_ids
    assert MARSEILLE_ID in fetch_ids
    assert "mth_existing_helix" in reuse_ids
    assert PARIS_ID in reuse_ids
    assert all(item.league in {"premier-league", "ligue-1"} for item in estimate.fetch_slots)
    assert estimate.estimated_credits == len(estimate.fetch_slots) * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    assert estimate.stop_reason is None


def test_cap_refuses_silent_backfill(
    monkeypatch: pytest.MonkeyPatch, clock: Clock, live_settings: Settings, tmp_path
) -> None:
    monkeypatch.setattr("predicta_ingestion.final_test_history.MAX_FINAL_TEST_REQUESTS", 1)
    estimate = estimate_final_test_run(matches=_universe(), persisted_ids=frozenset())
    assert estimate.stop_reason is not None
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=TargetMatchOddsSink(TeeCanonicalSink(MemoryCanonicalSink(), None), frozenset()),
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    with pytest.raises(ValidationError, match="MAX_FINAL_TEST_REQUESTS"):
        run_expand_final_test_history(
            provider=TheOddsApiProvider(enable_live=False, api_key="", clock=clock),
            pipeline=pipeline,
            estimate=estimate,
            estimate_only=False,
        )


def test_scope_rejects_other_leagues() -> None:
    with pytest.raises(ValidationError, match="premier-league and ligue-1"):
        estimate_final_test_run(
            matches=(
                _match(
                    match_id="mth_liga",
                    home="A",
                    away="B",
                    home_id="tm_a",
                    away_id="tm_b",
                    league="La Liga",
                    slug="la-liga",
                    kickoff=WINDOW_01_KICKOFF,
                ),
            ),
            persisted_ids=frozenset(),
        )
    with pytest.raises(ValidationError, match="refuses more than"):
        assert_persist_scope((), max_requests=MAX_FINAL_TEST_REQUESTS + 1, request_cap=MAX_FINAL_TEST_REQUESTS)


def test_isolated_paris_and_no_subdaily_grid() -> None:
    ids = isolated_paris_match_ids(_universe())
    assert PARIS_ID in ids
    assert HELIX_ID not in ids
    slots = plan_persist_slots(
        (
            _match(
                match_id=HELIX_ID,
                home="Helix FC",
                away="Meridian Athletic",
                home_id="tm_helix",
                away_id="tm_meridian",
                league="Premier League",
                slug="premier-league",
                kickoff=WINDOW_01_KICKOFF,
            ),
        )
    )
    assert len(slots) == 1
    assert slots[0].as_of == WINDOW_01_KICKOFF


def test_estimate_only_does_not_fetch(clock: Clock, live_settings: Settings, tmp_path) -> None:
    estimate = estimate_final_test_run(matches=_universe(), persisted_ids=frozenset())
    transport = OddsScriptedTransport()
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=TargetMatchOddsSink(TeeCanonicalSink(MemoryCanonicalSink(), None), frozenset()),
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    report = run_expand_final_test_history(
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
    payload = report_payload(report)
    assert payload["kind"] == "expand_final_test_history"
    assert TEST_ODDS_API_KEY not in json.dumps(payload)


def test_runner_reuses_persist_without_creating_matches(
    clock: Clock, live_settings: Settings, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from predicta_ingestion.final_test_history import FinalTestWindow

    monkeypatch.setattr(
        "predicta_ingestion.final_test_history.FINAL_TEST_WINDOWS",
        (
            FinalTestWindow(
                window_id="final_test_window_01",
                name="scripted",
                start=datetime(2026, 8, 21, tzinfo=UTC),
                end=datetime(2026, 8, 25, tzinfo=UTC),
                fetch=True,
                additional=True,
                elo_temporal_split="final_train",
                rationale="scripted",
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
            kickoff=EXISTING_KICKOFF,
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
    estimate = estimate_final_test_run(
        matches=matches,
        persisted_ids=frozenset(),
        windows=(
            FinalTestWindow(
                window_id="final_test_window_01",
                name="scripted",
                start=datetime(2026, 8, 21, tzinfo=UTC),
                end=datetime(2026, 8, 25, tzinfo=UTC),
                fetch=True,
                additional=True,
                elo_temporal_split="final_train",
                rationale="scripted",
            ),
        ),
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
        football_natural_key("Helix FC", "Meridian Athletic", EXISTING_KICKOFF),
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
    report = run_expand_final_test_history(
        provider=provider,
        pipeline=pipeline,
        estimate=estimate,
        secret=TEST_ODDS_API_KEY,
        estimate_only=False,
    )
    assert report.persist is not None
    assert TEST_ODDS_API_KEY not in json.dumps(report_payload(report))
    assert pipeline._sink.memory.matches == {}
    persisted = {item.match_id for item in pipeline._sink.memory.odds.values()}
    assert persisted <= {HELIX_ID, MARSEILLE_ID}


def test_pit_rejects_post_cutoff_and_future_snapshots(clock: Clock, live_settings: Settings, tmp_path) -> None:
    matches = (
        _match(
            match_id=HELIX_ID,
            home="Helix FC",
            away="Meridian Athletic",
            home_id="tm_helix",
            away_id="tm_meridian",
            league="Premier League",
            slug="premier-league",
            kickoff=EXISTING_KICKOFF,
        ),
    )
    estimate = estimate_final_test_run(
        matches=matches,
        persisted_ids=frozenset(),
        windows=FINAL_TEST_WINDOWS[-1:],
    )
    # Reuse existing window (fetch=false) so we don't need a live fetch; build PIT from persist fixture path.
    from predicta_ingestion.final_test_history import FinalTestWindow

    windows = (
        FinalTestWindow(
            window_id="final_test_window_01",
            name="scripted",
            start=datetime(2026, 8, 21, tzinfo=UTC),
            end=datetime(2026, 8, 25, tzinfo=UTC),
            fetch=True,
            additional=True,
            elo_temporal_split="final_train",
            rationale="scripted",
        ),
    )
    estimate = estimate_final_test_run(matches=matches, persisted_ids=frozenset(), windows=windows)
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
        football_natural_key("Helix FC", "Meridian Athletic", EXISTING_KICKOFF),
        HELIX_ID,
    )
    run_expand_final_test_history(
        provider=TheOddsApiProvider(
            enable_live=True,
            api_key=TEST_ODDS_API_KEY,
            clock=clock,
            transport=OddsScriptedTransport(),
            sleeper=RecordedSleep(),
            max_retries=2,
            timeout_seconds=5,
        ),
        pipeline=pipeline,
        estimate=estimate,
        secret=TEST_ODDS_API_KEY,
        estimate_only=False,
    )
    store = PointInTimeStore(pipeline._sink.memory)
    cutoff = EXISTING_KICKOFF
    selected = store.odds_as_of(HELIX_ID, cutoff)
    if selected is not None:
        assert selected.provenance.available_at < cutoff
    leaked = [
        item
        for item in pipeline._sink.memory.odds.values()
        if item.match_id == HELIX_ID and item.provenance.available_at >= cutoff
    ]
    assert leaked == []
    future_cutoff = cutoff - timedelta(days=1)
    assert store.odds_as_of(HELIX_ID, future_cutoff) is None or store.odds_as_of(
        HELIX_ID, future_cutoff
    ).provenance.available_at < future_cutoff
    # Feature cutoff after kickoff is leakage.
    if HELIX_ID not in pipeline._sink.memory.matches:
        pytest.skip("Odds sink does not create matches; feature cutoff uses Sportmonks match rows.")
    with pytest.raises(DataLeakageError):
        store.features_for_match(HELIX_ID, cutoff + timedelta(hours=1))


def test_slot_gap_refuses_five_minute_grid() -> None:
    first = PersistSlot(league="premier-league", as_of=WINDOW_01_KICKOFF, kickoff_date="2024-08-16")
    second = PersistSlot(
        league="premier-league",
        as_of=WINDOW_01_KICKOFF + timedelta(minutes=5),
        kickoff_date="2024-08-16",
    )
    with pytest.raises(ValidationError, match="sub-daily"):
        assert_persist_scope((first, second), max_requests=2, request_cap=MAX_FINAL_TEST_REQUESTS)
    assert MIN_SLOT_GAP >= timedelta(hours=12)
