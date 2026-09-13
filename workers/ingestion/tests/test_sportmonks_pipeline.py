from datetime import UTC, datetime

import pytest
from tests.conftest import TEST_SPORTMONKS_TOKEN
from tests.sportmonks_support import ScriptedTransport

from predicta_ingestion.canonical.enums import MatchStatus, ResolutionMethod, ResourceType, SportCode
from predicta_ingestion.cli import ingest_football
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import DataLeakageError
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.persistence.sql import SqlCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.errors import LiveIngestionDisabled, ProviderNotConfigured
from predicta_ingestion.providers.http import RecordedSleep
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.sportmonks import SportmonksFootballProvider
from predicta_ingestion.raw.store import FilesystemRawStore


def _sportmonks(clock, transport: ScriptedTransport) -> SportmonksFootballProvider:
    return SportmonksFootballProvider(
        enable_live=True,
        api_token=TEST_SPORTMONKS_TOKEN,
        clock=clock,
        transport=transport,
        sleeper=RecordedSleep(),
    )


def _request() -> ProviderRequest:
    return ProviderRequest(
        resource=ResourceType.FIXTURES,
        sport=SportCode.FOOTBALL,
        league="premier-league",
        since=datetime(2026, 9, 1, tzinfo=UTC),
        until=datetime(2026, 9, 14, tzinfo=UTC),
    )


def test_live_pipeline_normalizes_fixtures_and_provenance(live_pipeline: IngestionPipeline, clock) -> None:
    transport = ScriptedTransport()
    report = live_pipeline.run(_sportmonks(clock, transport), _request())
    assert report.data_mode.value == "live"
    assert report.records_accepted > 0
    sink = live_pipeline._sink
    assert isinstance(sink, MemoryCanonicalSink)
    scheduled = next(item for item in sink.matches.values() if item.status is MatchStatus.SCHEDULED)
    finished = next(item for item in sink.matches.values() if item.status is MatchStatus.FINISHED)
    assert scheduled.home_score is None
    assert scheduled.away_score is None
    assert finished.home_score == 2
    assert finished.away_score == 1
    assert scheduled.provenance.provider == "sportmonks"
    assert scheduled.provenance.data_mode.value == "live"
    assert scheduled.provenance.raw_payload_id
    assert scheduled.provenance.event_at == scheduled.kickoff_at
    assert finished.provenance.available_at > finished.kickoff_at
    assert finished.provenance.available_at <= clock.now()
    leagues = {item.name for item in sink.leagues.values()}
    assert "Premier League" in leagues
    teams = {item.name for item in sink.teams.values()}
    assert {"Arsenal", "Chelsea", "Liverpool", "Manchester City"} <= teams
    bindings = live_pipeline._resolver.bindings()
    assert bindings
    assert all(item.method is ResolutionMethod.EXACT_ID for item in bindings)
    assert all(item.confidence == 1.0 for item in bindings)


def test_raw_payload_is_immutable_and_checksummed(live_pipeline: IngestionPipeline, clock, tmp_path) -> None:
    transport = ScriptedTransport()
    first = live_pipeline.run(_sportmonks(clock, transport), _request())
    second = live_pipeline.run(_sportmonks(clock, transport), _request())
    assert first.duplicates == 0
    assert second.duplicates >= 1
    raw_files = list((tmp_path / "raw").rglob("*.json"))
    assert raw_files
    for path in raw_files:
        original = path.read_text(encoding="utf-8")
        path.write_text(original, encoding="utf-8")
        assert TEST_SPORTMONKS_TOKEN not in original


def test_point_in_time_hides_finished_result_before_kickoff(live_pipeline: IngestionPipeline, clock) -> None:
    live_pipeline.run(_sportmonks(clock, ScriptedTransport()), _request())
    sink = live_pipeline._sink
    assert isinstance(sink, MemoryCanonicalSink)
    finished = next(item for item in sink.matches.values() if item.status is MatchStatus.FINISHED)
    store = PointInTimeStore(sink)
    assert store.matches_finished_before(finished.kickoff_at) == []
    own = store.features_for_match(finished.id, finished.kickoff_at)
    assert finished.id not in own["prior_matches"]
    scheduled = next(item for item in sink.matches.values() if item.status is MatchStatus.SCHEDULED)
    later = store.features_for_match(scheduled.id, scheduled.kickoff_at)
    assert finished.id in later["prior_matches"]
    with pytest.raises(DataLeakageError):
        store.features_for_match(finished.id, clock.now())


def test_dry_run_does_not_write_sql_or_raw(clock, live_settings: Settings, tmp_path) -> None:
    statements: list[tuple[str, dict[object, object]]] = []
    sql = SqlCanonicalSink(clock=clock, executor=lambda sql, params: statements.append((sql, params)))
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=sql,
        resolver=IdentityResolver(clock),
        dry_run=True,
    )
    report = pipeline.run(_sportmonks(clock, ScriptedTransport()), _request())
    assert report.dry_run is True
    assert report.records_accepted > 0
    assert statements == []
    assert list((tmp_path / "raw").rglob("*.json")) == []


def test_sql_sink_records_raw_identity_and_match_upsert(clock, live_pipeline: IngestionPipeline) -> None:
    live_pipeline.run(_sportmonks(clock, ScriptedTransport()), _request())
    sink = live_pipeline._sink
    assert isinstance(sink, MemoryCanonicalSink)
    match = next(iter(sink.matches.values()))
    statements: list[tuple[str, dict[str, object]]] = []
    sql = SqlCanonicalSink(clock=clock, executor=lambda query, params: statements.append((query, params)))
    sql.record_raw(_first_raw(live_pipeline))
    sql.persist(_batch_from_sink(sink, match))
    sql.persist_identity(live_pipeline._resolver.bindings())
    joined = "\n".join(item[0] for item in statements)
    assert "INSERT INTO raw_payloads" in joined
    assert "ON CONFLICT (provider, checksum_sha256) DO NOTHING" in joined
    assert "INSERT INTO matches" in joined
    assert "ON CONFLICT (id) DO UPDATE SET" in joined
    assert "INSERT INTO provider_entity_maps" in joined
    assert all(TEST_SPORTMONKS_TOKEN not in str(params) for _sql, params in statements)


def _first_raw(pipeline: IngestionPipeline):
    store = pipeline._raw_store
    assert isinstance(store, FilesystemRawStore)
    raw_id = next(iter(store._checksums.values()))
    stored = store.get(raw_id)
    assert stored is not None
    return stored


def _batch_from_sink(sink: MemoryCanonicalSink, match):
    from predicta_ingestion.canonical.models import CanonicalBatch

    sport = next(iter(sink.sports.values()))
    league = next(item for item in sink.leagues.values() if item.id == match.league_id)
    teams = [item for item in sink.teams.values() if item.id in {match.home_team_id, match.away_team_id}]
    return CanonicalBatch(sports=[sport], leagues=[league], teams=teams, matches=[match])


def test_cli_refuses_live_when_disabled(live_pipeline: IngestionPipeline, settings: Settings) -> None:
    with pytest.raises(LiveIngestionDisabled):
        ingest_football(
            settings=settings,
            pipeline=live_pipeline,
            provider=_sportmonks(live_pipeline._clock, ScriptedTransport()),
        )


def test_cli_refuses_missing_token(clock, live_pipeline: IngestionPipeline) -> None:
    settings = Settings(_env_file=None, env="test", data_mode="live", enable_live=True, sportmonks_key="")
    with pytest.raises(ProviderNotConfigured):
        ingest_football(settings=settings, pipeline=live_pipeline, provider=_sportmonks(clock, ScriptedTransport()))


def test_cli_main_exits_when_live_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from predicta_ingestion.cli import main

    monkeypatch.setattr(
        "predicta_ingestion.cli.get_settings",
        lambda: Settings(_env_file=None, env="test", data_mode="mock", enable_live=False),
    )
    assert main(["ingest-football", "--league", "premier-league"]) == 1
    assert main(["ingest-history", "--league", "MLS"]) == 1


def test_cli_never_falls_back_to_mock(clock, live_settings: Settings, tmp_path) -> None:
    transport = ScriptedTransport()
    pipeline = IngestionPipeline(
        settings=live_settings,
        clock=clock,
        raw_store=FilesystemRawStore(tmp_path / "raw"),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
    )
    report = ingest_football(
        settings=live_settings,
        league="premier-league",
        date_from="2026-09-01",
        date_to="2026-09-14",
        provider=_sportmonks(clock, transport),
        pipeline=pipeline,
    )
    assert report.data_mode.value == "live"
    assert report.provider == "sportmonks"
    sink = pipeline._sink
    assert isinstance(sink, MemoryCanonicalSink)
    assert all(item.provenance.data_mode.value == "live" for item in sink.matches.values())
    assert not any("mock" in item.provenance.provider for item in sink.matches.values())
