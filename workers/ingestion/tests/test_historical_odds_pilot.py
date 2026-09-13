from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tests.the_odds_api_support import TEST_ODDS_API_KEY, OddsScriptedTransport

from predicta_ingestion.cli import ingest_odds
from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.historical_odds import (
    DEFAULT_AS_OF_AFTER,
    DEFAULT_AS_OF_BEFORE,
    DEFAULT_PIT_CUTOFF,
    MAX_PILOT_REQUESTS,
    PILOT_LEAGUES,
    VALUE_SNAPSHOT_RULE,
    assert_pilot_scope,
    complete_1x2,
    football_natural_key,
    next_historical_as_of,
    parse_odds_quota,
    run_historical_odds_pilot,
)
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.http import RecordedSleep
from predicta_ingestion.providers.the_odds_api import TheOddsApiProvider
from predicta_ingestion.raw.store import FilesystemRawStore


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


def _pipeline(clock: Clock, live_settings: Settings, tmp_path) -> IngestionPipeline:
    return IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
    )


def _bind_pilot_matches(pipeline: IngestionPipeline) -> dict[str, str]:
    ids = {
        "helix": "mth_football-sportmonks-helix-pilot",
        "bournemouth": "mth_football-sportmonks-bournemouth-pilot",
        "marseille": "mth_football-sportmonks-marseille-pilot",
    }
    pipeline._resolver.bind_match_natural_key(
        football_natural_key(
            "Helix FC",
            "Meridian Athletic",
            datetime(2026, 8, 16, 14, tzinfo=UTC),
        ),
        ids["helix"],
    )
    pipeline._resolver.bind_match_natural_key(
        "football|afc-bournemouth|brentford|2026-08-16T14:00:00+00:00",
        ids["bournemouth"],
    )
    pipeline._resolver.bind_match_natural_key(
        "football|olympique-marseille|monaco|2026-08-16T18:45:00+00:00",
        ids["marseille"],
    )
    return ids


def test_pilot_scope_rejects_backfill_leagues() -> None:
    with pytest.raises(ValidationError, match="premier-league and ligue-1"):
        assert_pilot_scope(("premier-league", "la-liga"), max_requests=4)
    with pytest.raises(ValidationError, match="refuses more than"):
        assert_pilot_scope(PILOT_LEAGUES, max_requests=MAX_PILOT_REQUESTS + 1)
    assert_pilot_scope(PILOT_LEAGUES, max_requests=4)


def test_quota_headers_are_parsed_without_inventing_credits() -> None:
    quota = parse_odds_quota(
        {"X-Requests-Used": "140", "x-requests-remaining": "360", "x-requests-last": "10"}
    )
    assert quota.requests_used == 140
    assert quota.requests_remaining == 360
    assert quota.requests_last == 10
    assert parse_odds_quota({}).requests_last is None


def test_next_timestamp_is_provider_owned_not_interpolated() -> None:
    nxt = next_historical_as_of(
        {
            "snapshot_timestamp": "2026-08-16T11:00:00Z",
            "previous_timestamp": "2026-08-16T10:55:00Z",
            "next_timestamp": "2026-08-16T11:05:00Z",
        }
    )
    assert nxt == datetime(2026, 8, 16, 11, 5, tzinfo=UTC)
    assert next_historical_as_of({"next_timestamp": None}) is None


def test_historical_pilot_parses_maps_matches_and_quarantines(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    transport = OddsScriptedTransport()
    pipeline = _pipeline(clock, live_settings, tmp_path)
    ids = _bind_pilot_matches(pipeline)
    report = run_historical_odds_pilot(
        provider=_provider(clock, transport),
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        pit_cutoff=DEFAULT_PIT_CUTOFF,
        secret=TEST_ODDS_API_KEY,
    )
    assert report.requests == 4
    assert report.credits_consumed == 40
    assert len(transport.calls) == 4
    assert {item.league for item in report.fetches} == {"premier-league", "ligue-1"}
    for fetch in report.fetches:
        assert fetch.snapshot_timestamp is not None
        assert fetch.previous_timestamp is not None
        assert fetch.next_timestamp is not None
        assert fetch.quota.requests_last == 10
        assert "historical_odds" in fetch.request_key
        assert TEST_ODDS_API_KEY not in fetch.request_key
        assert TEST_ODDS_API_KEY not in json.dumps(fetch.to_dict())

    assert report.identity.events == 5
    assert report.identity.matched == 3
    assert report.identity.rejected == 2
    assert report.identity.snapshots == 8
    assert report.identity.match_rate == pytest.approx(0.6)
    assert report.identity.false_match_count == 0
    assert report.identity.exact_matches == 1
    assert report.identity.alias_matches == 2
    assert "epl_unknown_borough_20260816" in report.identity.rejected_event_ids
    assert "fl1_paris_fc_angers_20260816" in report.identity.rejected_event_ids

    snapshots = list(pipeline._sink.odds.values())
    assert all(item.provenance.raw_payload_id for item in snapshots)
    assert all(item.provenance.available_at == item.provenance.collected_at for item in snapshots)
    assert {item.match_id for item in snapshots} == set(ids.values())
    helix = [item for item in snapshots if item.match_id == ids["helix"]]
    assert {item.bookmaker for item in helix} >= {"pinnacle", "betfair_ex_eu"}
    assert all(complete_1x2(item) for item in snapshots)
    bournemouth = next(item for item in snapshots if item.match_id == ids["bournemouth"])
    assert bournemouth.match_natural_key == "football|bournemouth|brentford|2026-08-16T14:00:00+00:00"
    marseille = next(item for item in snapshots if item.match_id == ids["marseille"])
    assert marseille.match_natural_key == "football|marseille|as-monaco|2026-08-16T18:45:00+00:00"
    assert "pinnacle" in report.bookmakers.bookmakers
    assert "pmu_fr" in report.bookmakers.bookmakers
    assert VALUE_SNAPSHOT_RULE in json.dumps(report.to_dict())
    assert TEST_ODDS_API_KEY not in json.dumps(report.to_dict())


def test_historical_pit_keeps_snapshot_before_t_and_hides_after(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    pipeline = _pipeline(clock, live_settings, tmp_path)
    ids = _bind_pilot_matches(pipeline)
    report = run_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        pit_cutoff=DEFAULT_PIT_CUTOFF,
        secret=TEST_ODDS_API_KEY,
    )
    assert report.pit.passed
    assert report.pit.match_id == ids["helix"]
    store = PointInTimeStore(pipeline._sink)
    selected = store.odds_as_of(ids["helix"], DEFAULT_PIT_CUTOFF)
    assert selected is not None
    assert selected.provenance.available_at < DEFAULT_PIT_CUTOFF
    home = next(item.decimal_odds for item in selected.selections if item.selection == "HOME")
    assert home == Decimal("1.82") or home == Decimal("1.80")
    leaked = store.odds_as_of(ids["helix"], datetime(2026, 8, 16, 10, 40, tzinfo=UTC))
    assert leaked is None
    post = [
        item
        for item in pipeline._sink.odds.values()
        if item.match_id == ids["helix"] and item.provenance.available_at >= DEFAULT_PIT_CUTOFF
    ]
    assert post
    assert all(item.provenance.available_at >= DEFAULT_PIT_CUTOFF for item in post)


def test_anti_leakage_refuses_future_features_and_post_cutoff_odds(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    from predicta_ingestion.canonical.enums import DataMode, MatchStatus
    from predicta_ingestion.canonical.models import Match, Provenance
    from predicta_ingestion.errors import DataLeakageError

    pipeline = _pipeline(clock, live_settings, tmp_path)
    ids = _bind_pilot_matches(pipeline)
    run_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        pit_cutoff=DEFAULT_PIT_CUTOFF,
        secret=TEST_ODDS_API_KEY,
    )
    kickoff = datetime(2026, 8, 16, 14, tzinfo=UTC)
    pipeline._sink.matches[ids["helix"]] = Match(
        id=ids["helix"],
        sport_id="spt_football",
        league_id="lge_premier-league",
        kickoff_at=kickoff,
        status=MatchStatus.FINISHED,
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_score=2,
        away_score=1,
        provenance=Provenance(
            provider="sportmonks",
            provider_id="helix",
            collected_at=kickoff,
            available_at=kickoff,
            event_at=kickoff,
            source="sportmonks",
            data_mode=DataMode.LIVE,
        ),
    )
    store = PointInTimeStore(pipeline._sink)
    with pytest.raises(DataLeakageError):
        store.features_for_match(ids["helix"], kickoff.replace(microsecond=1))
    features = store.features_for_match(ids["helix"], kickoff)
    assert ids["helix"] not in features["prior_matches"]
    odds = features["odds"]
    assert odds is not None
    assert odds.provenance.available_at < kickoff


def test_identical_historical_fetches_are_idempotent_and_append_only(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    transport = OddsScriptedTransport()
    pipeline = _pipeline(clock, live_settings, tmp_path)
    _bind_pilot_matches(pipeline)
    provider = _provider(clock, transport)
    first = run_historical_odds_pilot(
        provider=provider,
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        secret=TEST_ODDS_API_KEY,
    )
    snapshot_ids = set(pipeline._sink.odds)
    second = run_historical_odds_pilot(
        provider=provider,
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        secret=TEST_ODDS_API_KEY,
    )
    assert set(pipeline._sink.odds) == snapshot_ids
    assert second.identity.snapshots == first.identity.snapshots
    assert any(item["duplicates"] >= 1 for item in second.ingestion)
    helix_prices = sorted(
        {
            next(sel.decimal_odds for sel in item.selections if sel.selection == "HOME")
            for item in pipeline._sink.odds.values()
            if item.bookmaker == "pinnacle" and "helix" in item.match_id
        }
    )
    assert helix_prices == [Decimal("1.55"), Decimal("1.80")]


def test_raw_store_is_append_only_for_historical_envelopes(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    pipeline = _pipeline(clock, live_settings, tmp_path)
    _bind_pilot_matches(pipeline)
    run_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        secret=TEST_ODDS_API_KEY,
    )
    raw_files = list((tmp_path / "raw").rglob("*.json"))
    assert len(raw_files) == 4
    for path in raw_files:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text)
        assert payload["data_mode"] == "live"
        assert TEST_ODDS_API_KEY not in text
        decoded = json.loads(payload["body_utf8"])
        assert decoded["endpoint"] == "historical_odds"


def test_reproducible_reconstruction_same_dataset_cutoff_code(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    first_pipeline = _pipeline(clock, live_settings, tmp_path / "a")
    second_pipeline = _pipeline(clock, live_settings, tmp_path / "b")
    _bind_pilot_matches(first_pipeline)
    _bind_pilot_matches(second_pipeline)
    first = run_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=first_pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        pit_cutoff=DEFAULT_PIT_CUTOFF,
        secret=TEST_ODDS_API_KEY,
    )
    second = run_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=second_pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        pit_cutoff=DEFAULT_PIT_CUTOFF,
        secret=TEST_ODDS_API_KEY,
    )
    assert first.identity.to_dict() == second.identity.to_dict()
    assert {item.id: _prices(item) for item in first_pipeline._sink.odds.values()} == {
        item.id: _prices(item) for item in second_pipeline._sink.odds.values()
    }
    store_a = PointInTimeStore(first_pipeline._sink)
    store_b = PointInTimeStore(second_pipeline._sink)
    match_id = first.pit.match_id
    assert match_id is not None
    selected_a = store_a.odds_as_of(match_id, DEFAULT_PIT_CUTOFF)
    selected_b = store_b.odds_as_of(match_id, DEFAULT_PIT_CUTOFF)
    assert selected_a is not None and selected_b is not None
    assert selected_a.id == selected_b.id
    assert _prices(selected_a) == _prices(selected_b)


def test_bookmaker_selection_is_last_complete_not_best_ev(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    pipeline = _pipeline(clock, live_settings, tmp_path)
    ids = _bind_pilot_matches(pipeline)
    run_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        pit_cutoff=DEFAULT_PIT_CUTOFF,
        secret=TEST_ODDS_API_KEY,
    )
    store = PointInTimeStore(pipeline._sink)
    selected = store.odds_as_of(ids["helix"], DEFAULT_PIT_CUTOFF)
    assert selected is not None
    eligible = [
        item
        for item in pipeline._sink.odds.values()
        if item.match_id == ids["helix"] and item.provenance.available_at < DEFAULT_PIT_CUTOFF
    ]
    expected = max(eligible, key=lambda item: item.provenance.available_at)
    assert selected.bookmaker == expected.bookmaker
    assert selected.bookmaker == "betfair_ex_eu"
    pinnacle = next(item for item in eligible if item.bookmaker == "pinnacle")
    assert pinnacle.provenance.available_at < selected.provenance.available_at


def test_aliases_do_not_match_paris_fc_and_never_create_matches(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    pipeline = _pipeline(clock, live_settings, tmp_path)
    _bind_pilot_matches(pipeline)
    run_historical_odds_pilot(
        provider=_provider(clock, OddsScriptedTransport()),
        pipeline=pipeline,
        as_of_before=DEFAULT_AS_OF_BEFORE,
        as_of_after=DEFAULT_AS_OF_AFTER,
        secret=TEST_ODDS_API_KEY,
    )
    assert pipeline._sink.matches == {}
    details = " ".join(
        item.detail
        for diagnostic in pipeline._resolver.diagnostics
        if diagnostic.status == "quarantined"
        for item in [diagnostic]
    )
    assert "paris-fc" in details
    assert "unknown-borough" in details


def test_cli_historical_as_of_still_uses_one_snapshot(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    pipeline = _pipeline(clock, live_settings, tmp_path)
    pipeline._resolver.bind_match_natural_key(
        football_natural_key(
            "Helix FC",
            "Meridian Athletic",
            datetime(2026, 9, 8, 18, tzinfo=UTC),
        ),
        "mth_football-sportmonks-helix",
    )
    settings = live_settings.model_copy(update={"the_odds_api_key": TEST_ODDS_API_KEY})
    ingest_odds(
        settings=settings,
        league="premier-league",
        as_of="2026-09-08T15:55:00Z",
        pipeline=pipeline,
        provider=_provider(clock, OddsScriptedTransport()),
    )
    assert len(pipeline._sink.odds) == 1


def _prices(snapshot) -> dict[str, str]:
    return {item.selection: str(item.decimal_odds) for item in snapshot.selections}
