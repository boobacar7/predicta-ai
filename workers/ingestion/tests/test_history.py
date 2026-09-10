import json
from datetime import UTC, datetime
from urllib.parse import unquote, urlparse

from tests.conftest import TEST_SPORTMONKS_TOKEN
from tests.sportmonks_support import ScriptedTransport, assert_no_secret_in, load_sportmonks

from predicta_ingestion.canonical.enums import DataMode, MatchStatus, ResourceType, SportCode
from predicta_ingestion.cli import run_history
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.history import count_fixtures, ingest_history, memory_sink
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.normalization.sportmonks import SportmonksFootballNormalizer
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.errors import ProviderUnavailable
from predicta_ingestion.providers.http import RecordedSleep
from predicta_ingestion.providers.sportmonks import SportmonksFootballProvider
from predicta_ingestion.raw.envelope import RawEnvelope
from predicta_ingestion.raw.store import FilesystemRawStore, StoredRaw


def _provider(clock, transport: ScriptedTransport) -> SportmonksFootballProvider:
    return SportmonksFootballProvider(
        enable_live=True,
        api_token=TEST_SPORTMONKS_TOKEN,
        clock=clock,
        transport=transport,
        sleeper=RecordedSleep(),
    )


def _history_pipeline(clock, live_settings: Settings, tmp_path) -> IngestionPipeline:
    return IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
    )


def test_mls_history_ingest_is_idempotent(clock, live_settings: Settings, tmp_path) -> None:
    pipeline = _history_pipeline(clock, live_settings, tmp_path)
    provider = _provider(clock, ScriptedTransport())
    first = ingest_history(provider=provider, pipeline=pipeline, clock=clock, league="MLS")
    second = ingest_history(provider=provider, pipeline=pipeline, clock=clock, league="MLS")
    sink = memory_sink(pipeline)
    assert sum(item.inserted_count for item in first.seasons) == len(sink.matches)
    assert sum(item.inserted_count for item in second.seasons) == 0
    assert sum(item.duplicate_count for item in second.seasons) >= 1
    assert len({item.id for item in sink.matches.values()}) == len(sink.matches)
    for path in (tmp_path / "raw").rglob("*.json"):
        assert TEST_SPORTMONKS_TOKEN not in path.read_text(encoding="utf-8")


def test_history_quality_report_counts_mls_seasons(clock, live_settings: Settings, tmp_path) -> None:
    pipeline = _history_pipeline(clock, live_settings, tmp_path)
    report = ingest_history(
        provider=_provider(clock, ScriptedTransport()),
        pipeline=pipeline,
        clock=clock,
        league="mls",
    )
    discovered = {item["season"] for item in report.discovered}
    assert discovered == {"2023", "2024", "2025"}
    by_season = {item.season: item for item in report.seasons}
    assert by_season["2023"].fetched_count == 1
    assert by_season["2024"].fetched_count == 3
    assert by_season["2025"].fetched_count == 1
    assert by_season["2023"].normalized_count == 1
    assert by_season["2024"].normalized_count == 3
    assert by_season["2024"].missing_score_count >= 1
    assert "ambiguous_identity" not in by_season["2023"].quarantined_reasons
    assert "ambiguous_identity" not in by_season["2024"].quarantined_reasons
    assert "ambiguous_identity" not in by_season["2025"].quarantined_reasons
    assert all(item.status != "quarantined" for item in report.identity)
    assert all(item.provider == "sportmonks" for item in report.seasons)
    assert all(item.data_mode == "live" for item in report.seasons)
    assert all(item.ingestion_run_id == report.ingestion_run_id for item in report.seasons)
    sink = memory_sink(pipeline)
    for match in sink.matches.values():
        assert match.provenance.provider == "sportmonks"
        assert match.provenance.raw_payload_id
        assert match.provenance.event_at == match.kickoff_at
        assert match.kickoff_at.tzinfo is not None


def test_history_fetch_uses_documented_season_and_fixture_endpoints(
    clock, live_settings: Settings, tmp_path
) -> None:
    transport = ScriptedTransport()
    pipeline = _history_pipeline(clock, live_settings, tmp_path)
    ingest_history(
        provider=_provider(clock, transport),
        pipeline=pipeline,
        clock=clock,
        league="mls",
        season="18001",
    )
    urls = [url for url, _headers in transport.calls]
    decoded = [unquote(url) for url in urls]
    assert any(urlparse(url).path.rstrip("/").endswith("/seasons") for url in urls)
    assert any("seasonLeagues:779" in url for url in decoded)
    assert any(
        urlparse(url).path.rstrip("/").endswith("/fixtures") and "fixtureSeasons:18001" in unquote(url)
        for url in urls
    )
    assert not any("/fixtures/seasons/" in url for url in urls)
    assert not any("/leagues/779" in url and "seasons" in url for url in urls)
    assert all("api_token" not in url for url in urls)
    for url, headers in transport.calls:
        assert_no_secret_in(url)
        assert headers["Authorization"] == TEST_SPORTMONKS_TOKEN


def test_history_http_404_is_not_swallowed(clock, live_settings: Settings, tmp_path) -> None:
    transport = ScriptedTransport()
    transport.not_found_substrings = ["/fixtures"]
    pipeline = _history_pipeline(clock, live_settings, tmp_path)
    try:
        ingest_history(
            provider=_provider(clock, transport),
            pipeline=pipeline,
            clock=clock,
            league="mls",
            season="18001",
        )
    except ProviderUnavailable as exc:
        message = str(exc)
        assert "HTTP 404" in message
        assert "/fixtures" in message
        assert TEST_SPORTMONKS_TOKEN not in message
        assert_no_secret_in(exc)
    else:
        raise AssertionError("HTTP 404 must not be swallowed by a mock fallback")


def test_season_with_date_window_uses_between_filter(clock, live_settings: Settings, tmp_path) -> None:
    transport = ScriptedTransport()
    pipeline = _history_pipeline(clock, live_settings, tmp_path)
    report = ingest_history(
        provider=_provider(clock, transport),
        pipeline=pipeline,
        clock=clock,
        league="mls",
        season="2024",
        date_from=datetime(2024, 9, 1, tzinfo=UTC),
        date_to=datetime(2024, 9, 10, 23, 59, 59, tzinfo=UTC),
    )
    assert [item.season for item in report.seasons] == ["2024"]
    assert report.seasons[0].normalized_count == 1
    urls = [url for url, _headers in transport.calls]
    assert any("/fixtures/between/2024-09-01/2024-09-10" in url for url in urls)
    assert any("fixtureSeasons" in url and "18001" in url for url in urls)


def test_per_fixture_quarantine_keeps_valid_neighbours(clock) -> None:
    normalizer = SportmonksFootballNormalizer(clock)
    envelope = RawEnvelope(
        provider="sportmonks",
        resource=ResourceType.FIXTURES,
        request_key="sportmonks:fixtures:quarantine",
        collected_at=clock.now(),
        data_mode=DataMode.LIVE,
        sport=SportCode.FOOTBALL,
        body=load_sportmonks("mls_fixtures_quarantine.json"),
        content_type="application/json",
        headers={},
    )
    stored = StoredRaw(raw_id="raw_test", envelope=envelope, storage_uri="mem", duplicate=False)
    payload = json.loads(envelope.body.decode("utf-8"))
    batch = normalizer.normalize(stored, payload)
    reasons = {item.reason_code for item in normalizer.quarantined}
    assert "placeholder_fixture" in reasons
    assert "invalid_payload" in reasons
    assert "same_team" in reasons
    assert len(batch.matches) == 1
    assert batch.matches[0].status is MatchStatus.FINISHED


def test_seasons_payload_is_not_normalized_as_fixtures(clock) -> None:
    normalizer = SportmonksFootballNormalizer(clock)
    envelope = RawEnvelope(
        provider="sportmonks",
        resource=ResourceType.SEASONS,
        request_key="sportmonks:seasons:779",
        collected_at=clock.now(),
        data_mode=DataMode.LIVE,
        sport=SportCode.FOOTBALL,
        body=load_sportmonks("seasons_mls.json"),
        content_type="application/json",
        headers={},
    )
    stored = StoredRaw(raw_id="raw_seasons", envelope=envelope, storage_uri="mem", duplicate=False)
    payload = json.loads(envelope.body.decode("utf-8"))
    batch = normalizer.normalize(stored, payload)
    assert batch.matches == []
    assert {item.season for item in batch.leagues} == {"2023", "2024", "2025"}
    assert all(item.name == "Major League Soccer" for item in batch.leagues)
    assert all(item.reason_code != "unknown_status" for item in normalizer.quarantined)
    assert "unknown_status" not in {item.reason_code for item in normalizer.quarantined}


def test_count_fixtures_does_not_treat_league_payload_as_matches() -> None:
    envelope = RawEnvelope(
        provider="sportmonks",
        resource=ResourceType.SEASONS,
        request_key="sportmonks:seasons:779",
        collected_at=datetime(2026, 9, 9, tzinfo=UTC),
        data_mode=DataMode.LIVE,
        sport=SportCode.FOOTBALL,
        body=load_sportmonks("league_mls.json"),
        content_type="application/json",
        headers={},
    )
    assert count_fixtures([envelope]) == 0


def test_cli_history_dry_run_builds_dataset_without_raw(clock, live_settings: Settings, tmp_path) -> None:
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    report, dataset = run_history(
        settings=live_settings,
        league="mls",
        dry_run=True,
        build_dataset=True,
        provider=_provider(clock, ScriptedTransport()),
        pipeline=pipeline,
        clock=clock,
    )
    assert report.dry_run is True
    assert list((tmp_path / "raw").rglob("*.json")) == []
    assert dataset is not None
    assert len(dataset.observations) >= 1
    assert dataset.standings_available is False


def test_unknown_season_is_rejected(clock, live_settings: Settings, tmp_path) -> None:
    pipeline = _history_pipeline(clock, live_settings, tmp_path)
    try:
        ingest_history(
            provider=_provider(clock, ScriptedTransport()),
            pipeline=pipeline,
            clock=clock,
            league="mls",
            season="1999",
        )
    except ValidationError as exc:
        assert exc.reason_code == "unknown_season"
    else:
        raise AssertionError("unknown seasons must fail")


def test_european_history_does_not_fetch_uncapped_seasons(clock, live_settings: Settings, tmp_path) -> None:
    transport = ScriptedTransport()
    pipeline = _history_pipeline(clock, live_settings, tmp_path)
    report = ingest_history(
        provider=_provider(clock, transport),
        pipeline=pipeline,
        clock=clock,
        league="premier-league",
    )
    selected = {item["season"] for item in report.discovered if item["selected"]}
    assert "2023/2024" not in selected
    urls = [url for url, _ in transport.calls]
    decoded = [unquote(url) for url in urls]
    assert not any("fixtureSeasons:23611" in url for url in decoded)
    assert any("fixtureSeasons:23614" in url for url in decoded)
    assert not any("/fixtures/seasons/" in url for url in urls)
