from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from tests.the_odds_api_support import TEST_ODDS_API_KEY, OddsScriptedTransport

from predicta_ingestion.canonical.enums import ResourceType
from predicta_ingestion.cli import ingest_odds
from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.normalization.odds import CANONICAL_1X2_MARKET, football_1x2_selection
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.persistence.sql import SqlCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.errors import (
    LiveIngestionDisabled,
    ProviderAuthError,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderUnavailable,
)
from predicta_ingestion.providers.http import RecordedSleep
from predicta_ingestion.providers.mock import MockFootballProvider, MockOddsProvider
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.the_odds_api import LIVE_ODDS_SOURCE, TheOddsApiProvider
from predicta_ingestion.raw.store import FilesystemRawStore
from predicta_ingestion.secrets import redact_url


def _provider(
    clock: Clock,
    transport: OddsScriptedTransport,
    *,
    enable_live: bool = True,
    api_key: str = TEST_ODDS_API_KEY,
) -> TheOddsApiProvider:
    return TheOddsApiProvider(
        enable_live=enable_live,
        api_key=api_key,
        clock=clock,
        transport=transport,
        sleeper=RecordedSleep(),
        max_retries=2,
        timeout_seconds=5,
    )


def _live_pipeline(clock: Clock, live_settings: Settings, tmp_path) -> IngestionPipeline:
    return IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
    )


def _bind_fixture_match(pipeline: IngestionPipeline, canonical_id: str = "mth_football-sportmonks-helix") -> str:
    pipeline._resolver.bind_match_natural_key(
        "football|helix-fc|meridian-athletic|2026-09-08T18:00:00+00:00",
        canonical_id,
    )
    return canonical_id


def test_live_disabled_does_not_call_network(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    provider = _provider(clock, transport, enable_live=False)
    with pytest.raises(LiveIngestionDisabled):
        provider.fetch(ProviderRequest(resource=ResourceType.ODDS, league="premier-league"))
    assert transport.calls == []


def test_missing_key_is_not_configured(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    provider = _provider(clock, transport, api_key="")
    with pytest.raises(ProviderNotConfigured):
        provider.fetch(ProviderRequest(resource=ResourceType.ODDS, league="premier-league"))
    assert transport.calls == []


def test_fetch_wraps_array_and_puts_key_in_query(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    provider = _provider(clock, transport)
    envelopes = provider.fetch(ProviderRequest(resource=ResourceType.ODDS, league="premier-league"))
    assert len(envelopes) == 1
    payload = json.loads(envelopes[0].body.decode("utf-8"))
    assert payload["data_mode"] == "live"
    assert payload["provider"] == "the_odds_api"
    assert payload["source"] == LIVE_ODDS_SOURCE
    assert payload["sport_key"] == "soccer_epl"
    assert payload["endpoint"] == "odds"
    assert len(payload["data"]) == 1
    url, headers = transport.calls[0]
    query = parse_qs(urlparse(url).query)
    assert query["apiKey"] == [TEST_ODDS_API_KEY]
    assert query["regions"] == ["eu"]
    assert query["markets"] == ["h2h"]
    assert query["oddsFormat"] == ["decimal"]
    assert "Authorization" not in headers
    assert TEST_ODDS_API_KEY not in redact_url(url, TEST_ODDS_API_KEY)


def test_historical_fetch_uses_documented_date_parameter(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    provider = _provider(clock, transport)
    as_of = datetime(2026, 9, 8, 15, 55, tzinfo=UTC)
    envelopes = provider.fetch(
        ProviderRequest(resource=ResourceType.ODDS, league="premier-league", as_of=as_of)
    )
    payload = json.loads(envelopes[0].body.decode("utf-8"))
    assert payload["endpoint"] == "historical_odds"
    assert payload["snapshot_timestamp"] == "2026-09-08T15:55:00Z"
    url, _headers = transport.calls[0]
    assert "/v4/historical/sports/soccer_epl/odds" in url
    assert "date=2026-09-08T15%3A55%3A00Z" in url or "date=2026-09-08T15:55:00Z" in url


def test_historical_fetch_can_override_sport_key_for_champions_league_qualification(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    provider = _provider(clock, transport)
    as_of = datetime(2026, 7, 7, 16, 0, tzinfo=UTC)
    envelopes = provider.fetch(
        ProviderRequest(
            resource=ResourceType.ODDS,
            league="champions-league",
            as_of=as_of,
            sport_key="soccer_uefa_champs_league_qualification",
        )
    )
    payload = json.loads(envelopes[0].body.decode("utf-8"))
    assert payload["sport_key"] == "soccer_uefa_champs_league_qualification"
    assert payload["league_slug"] == "champions-league"
    url, _headers = transport.calls[0]
    assert "/v4/historical/sports/soccer_uefa_champs_league_qualification/odds" in url
    assert TEST_ODDS_API_KEY not in envelopes[0].request_key


def test_http_401_is_auth_error_without_secret(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    transport.force_status = 401
    transport.force_body = b'{"message":"INVALID_KEY"}'
    provider = _provider(clock, transport)
    with pytest.raises(ProviderAuthError) as exc:
        provider.fetch(ProviderRequest(resource=ResourceType.ODDS, league="premier-league"))
    assert TEST_ODDS_API_KEY not in str(exc.value)


def test_http_429_exhausted_raises_rate_limited(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    transport.rate_limit_remaining = 10
    provider = _provider(clock, transport)
    with pytest.raises(ProviderRateLimited):
        provider.fetch(ProviderRequest(resource=ResourceType.ODDS, league="premier-league"))


def test_invalid_json_is_unavailable(clock: Clock) -> None:
    transport = OddsScriptedTransport()
    transport.invalid_json_once = True
    provider = _provider(clock, transport)
    with pytest.raises(ProviderUnavailable, match="JSON"):
        provider.fetch(ProviderRequest(resource=ResourceType.ODDS, league="premier-league"))


def test_mapping_h2h_to_canonical_1x2(clock: Clock, live_settings: Settings, tmp_path) -> None:
    transport = OddsScriptedTransport()
    pipeline = _live_pipeline(clock, live_settings, tmp_path)
    _bind_fixture_match(pipeline)
    pipeline.run(_provider(clock, transport), ProviderRequest(resource=ResourceType.ODDS, league="premier-league"))
    snapshots = list(pipeline._sink.odds.values())
    assert snapshots
    complete = [item for item in snapshots if {sel.selection for sel in item.selections} == {"HOME", "DRAW", "AWAY"}]
    assert complete
    pinnacle = next(item for item in complete if item.bookmaker == "pinnacle")
    assert pinnacle.market == CANONICAL_1X2_MARKET
    assert pinnacle.provenance.source == LIVE_ODDS_SOURCE
    assert pinnacle.provenance.data_mode.value == "live"
    assert pinnacle.provenance.raw_payload_id
    prices = {item.selection: item.decimal_odds for item in pinnacle.selections}
    assert prices["HOME"] == Decimal("1.85")
    assert prices["DRAW"] == Decimal("3.6")
    assert prices["AWAY"] == Decimal("4.2")
    assert not hasattr(pinnacle, "implied_probability_raw")


def test_unknown_outcome_is_not_invented() -> None:
    assert football_1x2_selection("Helix FC", home_team="Helix FC", away_team="Meridian Athletic") == "HOME"
    assert football_1x2_selection("Draw", home_team="Helix FC", away_team="Meridian Athletic") == "DRAW"
    assert football_1x2_selection("Yes", home_team="Helix FC", away_team="Meridian Athletic") is None


def test_incomplete_market_and_missing_bookmaker_are_not_filled(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    transport = OddsScriptedTransport()
    transport.current_body = "incomplete_and_missing.json"
    pipeline = _live_pipeline(clock, live_settings, tmp_path)
    _bind_fixture_match(pipeline)
    report = pipeline.run(
        _provider(clock, transport), ProviderRequest(resource=ResourceType.ODDS, league="premier-league")
    )
    snapshots = list(pipeline._sink.odds.values())
    assert len(snapshots) == 1
    assert {item.selection for item in snapshots[0].selections} == {"HOME", "AWAY"}
    assert any(item.reason_code == "missing_timestamp" for item in report.quarantined)


def test_identical_fetches_are_idempotent(clock: Clock, live_settings: Settings, tmp_path) -> None:
    transport = OddsScriptedTransport()
    pipeline = _live_pipeline(clock, live_settings, tmp_path)
    _bind_fixture_match(pipeline)
    request = ProviderRequest(resource=ResourceType.ODDS, league="premier-league")
    provider = _provider(clock, transport)
    pipeline.run(provider, request)
    second = pipeline.run(provider, request)
    assert second.duplicates >= 1
    assert len(pipeline._sink.odds) == 2


def test_price_change_appends_new_snapshot(clock: Clock, live_settings: Settings, tmp_path) -> None:
    transport = OddsScriptedTransport()
    pipeline = _live_pipeline(clock, live_settings, tmp_path)
    _bind_fixture_match(pipeline)
    provider = _provider(clock, transport)
    pipeline.run(
        provider,
        ProviderRequest(
            resource=ResourceType.ODDS,
            league="premier-league",
            as_of=datetime(2026, 9, 8, 15, 55, tzinfo=UTC),
        ),
    )
    transport.historical_body = "soccer_epl_historical_later.json"
    pipeline.run(
        provider,
        ProviderRequest(
            resource=ResourceType.ODDS,
            league="premier-league",
            as_of=datetime(2026, 9, 8, 16, 5, tzinfo=UTC),
        ),
    )
    pinnacle = [item for item in pipeline._sink.odds.values() if item.bookmaker == "pinnacle"]
    assert len(pinnacle) == 2
    prices = sorted(item.selections[0].decimal_odds for item in pinnacle)
    assert prices == [Decimal("1.80"), Decimal("1.92")]


def test_pit_hides_post_cutoff_and_keeps_earlier_snapshot(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    transport = OddsScriptedTransport()
    pipeline = _live_pipeline(clock, live_settings, tmp_path)
    canonical_id = _bind_fixture_match(pipeline)
    provider = _provider(clock, transport)
    pipeline.run(
        provider,
        ProviderRequest(
            resource=ResourceType.ODDS,
            league="premier-league",
            as_of=datetime(2026, 9, 8, 15, 55, tzinfo=UTC),
        ),
    )
    pipeline.run(
        provider,
        ProviderRequest(
            resource=ResourceType.ODDS,
            league="premier-league",
            as_of=datetime(2026, 9, 8, 16, 5, tzinfo=UTC),
        ),
    )
    snapshot = next(iter(pipeline._sink.odds.values()))
    assert snapshot.match_id == canonical_id
    store = PointInTimeStore(pipeline._sink)
    cutoff = datetime(2026, 9, 8, 16, 0, tzinfo=UTC)
    selected = store.odds_as_of(snapshot.match_id, cutoff)
    assert selected is not None
    assert selected.provenance.available_at < cutoff
    home = next(item.decimal_odds for item in selected.selections if item.selection == "HOME")
    assert home == Decimal("1.80")
    leaked = store.odds_as_of(snapshot.match_id, datetime(2026, 9, 8, 15, 40, tzinfo=UTC))
    assert leaked is None


def test_live_odds_link_to_football_match_via_natural_key(
    clock: Clock,
    live_settings: Settings,
    tmp_path,
    pipeline: IngestionPipeline,
    football_provider: MockFootballProvider,
) -> None:
    pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    match = next(iter(pipeline._sink.matches.values()))
    live_pipeline = _live_pipeline(clock, live_settings, tmp_path)
    assert match.natural_key is not None
    live_pipeline._resolver.bind_match_natural_key(match.natural_key, match.id)
    live_pipeline.run(
        _provider(clock, OddsScriptedTransport()),
        ProviderRequest(resource=ResourceType.ODDS, league="premier-league"),
    )
    snapshot = next(item for item in live_pipeline._sink.odds.values() if item.bookmaker == "pinnacle")
    assert snapshot.match_id == match.id


def test_unmatched_live_odds_are_quarantined_not_persisted(
    clock: Clock, live_settings: Settings, tmp_path
) -> None:
    pipeline = _live_pipeline(clock, live_settings, tmp_path)
    report = pipeline.run(
        _provider(clock, OddsScriptedTransport()),
        ProviderRequest(resource=ResourceType.ODDS, league="premier-league"),
    )
    assert pipeline._sink.odds == {}
    unmatched = [item for item in report.quarantined if item.reason_code == "unmatched_odds_event"]
    assert unmatched
    assert "No Sportmonks match" in unmatched[0].detail
    assert "helix-fc" in unmatched[0].detail
    assert "meridian-athletic" in unmatched[0].detail


def test_mock_provider_never_used_when_live_errors(clock: Clock, live_settings: Settings, tmp_path) -> None:
    transport = OddsScriptedTransport()
    transport.force_status = 503
    transport.force_body = b'{"message":"unavailable"}'
    pipeline = _live_pipeline(clock, live_settings, tmp_path)
    with pytest.raises(ProviderUnavailable):
        pipeline.run(
            _provider(clock, transport),
            ProviderRequest(resource=ResourceType.ODDS, league="premier-league"),
        )
    assert pipeline._sink.odds == {}
    mock = MockOddsProvider(clock)
    assert mock.name != "the_odds_api"


def test_cli_refuses_odds_without_key(clock: Clock, live_settings: Settings, tmp_path) -> None:
    settings = Settings(_env_file=None, env="test", data_mode="live", enable_live=True, the_odds_api_key="")
    with pytest.raises(ProviderNotConfigured):
        ingest_odds(
            settings=settings,
            pipeline=_live_pipeline(clock, live_settings, tmp_path),
            provider=_provider(clock, OddsScriptedTransport()),
        )


def test_sql_odds_insert_is_append_only_without_value_metrics(clock: Clock) -> None:
    statements: list[tuple[str, dict[str, object]]] = []
    sql = SqlCanonicalSink(clock=clock, executor=lambda query, params: statements.append((query, params)))
    from predicta_ingestion.canonical.enums import DataMode
    from predicta_ingestion.canonical.models import CanonicalBatch, OddsSelection, OddsSnapshot, Provenance

    snapshot = OddsSnapshot(
        id="odd_test_1",
        match_id="mth_test",
        market="1X2",
        bookmaker="pinnacle",
        selections=[
            OddsSelection(selection="HOME", label="Helix FC", decimal_odds=Decimal("1.85")),
            OddsSelection(selection="DRAW", label="Draw", decimal_odds=Decimal("3.6")),
            OddsSelection(selection="AWAY", label="Meridian Athletic", decimal_odds=Decimal("4.2")),
        ],
        provenance=Provenance(
            provider="the_odds_api",
            provider_id="evt:pinnacle:1X2:2026-09-08T16:00:00+00:00",
            collected_at=datetime(2026, 9, 8, 16, tzinfo=UTC),
            available_at=datetime(2026, 9, 8, 16, tzinfo=UTC),
            source=LIVE_ODDS_SOURCE,
            data_mode=DataMode.LIVE,
            raw_payload_id="raw_test",
        ),
    )
    sql.persist(CanonicalBatch(odds=[snapshot]))
    joined = "\n".join(item[0] for item in statements)
    assert "INSERT INTO odds_snapshots" in joined
    assert "WHERE EXISTS (SELECT 1 FROM matches WHERE id = :existing_match_id)" in joined
    assert "ON CONFLICT (id) DO NOTHING" in joined
    assert "INSERT INTO odds_selections" in joined
    assert all(params.get("overround") is None for _sql, params in statements if "overround" in params)
    assert all(params.get("implied") is None for _sql, params in statements if "implied" in params)
