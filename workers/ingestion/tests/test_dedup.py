import json
from pathlib import Path

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.mock import MockFootballProvider, MockOddsProvider
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.raw.envelope import RawEnvelope
from predicta_ingestion.raw.store import FilesystemRawStore


def test_raw_checksum_deduplicates(pipeline: IngestionPipeline, football_provider: MockFootballProvider) -> None:
    first = pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    second = pipeline.run(football_provider, ProviderRequest(resource=ResourceType.FIXTURES))
    assert first.duplicates == 0
    assert second.duplicates == 1
    assert len(pipeline._sink.matches) == 1


def test_odds_snapshot_natural_key_deduplicates(pipeline: IngestionPipeline, odds_provider: MockOddsProvider) -> None:
    pipeline.run(odds_provider, ProviderRequest(resource=ResourceType.ODDS))
    pipeline.run(odds_provider, ProviderRequest(resource=ResourceType.ODDS))
    assert len(pipeline._sink.odds) == 1


def _sportmonks_envelope(*, remaining: int, billed_at: int = 1789039000) -> RawEnvelope:
    payload = {
        "data": [{"id": 19137588, "name": "LA Galaxy vs Inter Miami"}],
        "pagination": {
            "count": 1,
            "current_page": 1,
            "has_more": False,
            "next_cursor": f"https://api.sportmonks.com/v3/football/fixtures?page={remaining}",
        },
        "rate_limit": {"remaining": remaining, "requested_entity": "fixture"},
        "subscription": [{"meta": {"current_timestamp": billed_at}, "plans": [{"plan": "Growth"}]}],
    }
    return RawEnvelope(
        provider="sportmonks",
        resource=ResourceType.FIXTURES,
        request_key="sportmonks:football:fixtures:mls:24962",
        collected_at="2026-09-10T12:00:00Z",
        data_mode=DataMode.LIVE,
        sport=SportCode.FOOTBALL,
        body=json.dumps(payload).encode("utf-8"),
    )


def test_sportmonks_checksum_ignores_rate_limit() -> None:
    first = _sportmonks_envelope(remaining=2800, billed_at=1789039000)
    second = _sportmonks_envelope(remaining=2799, billed_at=1789039123)
    assert first.checksum_sha256 == second.checksum_sha256


def test_filesystem_raw_store_indexes_existing_files_across_processes(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    stored = FilesystemRawStore(root).put(_sportmonks_envelope(remaining=2800))
    assert stored.duplicate is False
    files = list(root.rglob("*.json"))
    assert len(files) == 1

    replay = FilesystemRawStore(root).put(_sportmonks_envelope(remaining=2799, billed_at=99))
    assert replay.duplicate is True
    assert replay.id == stored.id
    assert len(list(root.rglob("*.json"))) == 1


def test_filesystem_raw_store_recomputes_checksum_when_stored_hash_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    stored = FilesystemRawStore(root).put(_sportmonks_envelope(remaining=2800, billed_at=1))
    path = next((tmp_path / "raw").rglob("*.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["checksum_sha256"] = "stale" * 8
    path.write_text(json.dumps(payload), encoding="utf-8")

    replay = FilesystemRawStore(root).put(_sportmonks_envelope(remaining=1, billed_at=99))
    assert replay.duplicate is True
    assert replay.id == stored.id
    assert len(list(root.rglob("*.json"))) == 1
