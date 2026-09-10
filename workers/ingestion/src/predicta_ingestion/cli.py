from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine

from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.config import Settings, get_settings
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.ids import stable_entity_id
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.persistence.sql import SqlCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline, IngestionReport
from predicta_ingestion.providers.errors import LiveIngestionDisabled, ProviderError, ProviderNotConfigured
from predicta_ingestion.providers.http import HttpxTransport
from predicta_ingestion.providers.leagues import V1_FOOTBALL_LEAGUES
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.sportmonks import SportmonksFootballProvider
from predicta_ingestion.raw.store import FilesystemRawStore
from predicta_ingestion.secrets import redact_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m predicta_ingestion",
        description="PREDICTA football ingestion. Live Sportmonks is opt-in and never falls back to mock.",
    )
    sub = parser.add_subparsers(dest="command")
    ingest = sub.add_parser("ingest-football", help="Ingest V1 football leagues and fixtures from Sportmonks.")
    ingest.add_argument(
        "--league",
        default="all",
        help="V1 league slug or 'all'. " + ", ".join(item.slug for item in V1_FOOTBALL_LEAGUES),
    )
    ingest.add_argument("--date-from", dest="date_from", help="UTC start date YYYY-MM-DD (inclusive).")
    ingest.add_argument("--date-to", dest="date_to", help="UTC end date YYYY-MM-DD (inclusive).")
    ingest.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch, validate and normalize without writing PostgreSQL.",
    )
    args = parser.parse_args(argv)
    if args.command != "ingest-football":
        parser.print_help()
        return 2
    try:
        settings = get_settings()
        report = ingest_football(
            settings=settings,
            league=args.league,
            date_from=args.date_from,
            date_to=args.date_to,
            dry_run=args.dry_run,
        )
    except (LiveIngestionDisabled, ProviderNotConfigured, ProviderError, RuntimeError) as exc:
        print(redact_text(str(exc)), file=sys.stderr)
        return 1
    print(json.dumps(_report_payload(report), indent=2, sort_keys=True))
    return 0


def ingest_football(
    *,
    settings: Settings,
    league: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
    dry_run: bool = False,
    provider: SportmonksFootballProvider | None = None,
    pipeline: IngestionPipeline | None = None,
) -> IngestionReport:
    _assert_live_ready(settings)
    clock = Clock()
    sportmonks = provider or SportmonksFootballProvider(
        enable_live=settings.enable_live,
        api_token=settings.sportmonks_key,
        clock=clock,
        transport=HttpxTransport(),
        base_url=settings.sportmonks_base_url,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
    )
    active_pipeline = pipeline or _build_pipeline(settings, clock, dry_run=dry_run)
    request = ProviderRequest(
        resource=ResourceType.FIXTURES,
        sport=SportCode.FOOTBALL,
        league=league,
        since=_parse_date(date_from, end_of_day=False) if date_from else None,
        until=_parse_date(date_to, end_of_day=True) if date_to else None,
    )
    report = active_pipeline.run(sportmonks, request)
    if not dry_run and isinstance(getattr(active_pipeline, "_sink", None), SqlCanonicalSink):
        sink = active_pipeline._sink
        if isinstance(sink, SqlCanonicalSink):
            sink.record_run(
                run_id=stable_entity_id("run", "sportmonks", clock.now().isoformat()),
                provider="sportmonks",
                resource_type=ResourceType.FIXTURES.value,
                status="completed" if not report.quarantined else "completed_with_quarantine",
                data_mode=report.data_mode.value,
                records_read=report.records_read,
                records_accepted=report.records_accepted,
                records_quarantined=len(report.quarantined),
            )
    return report


def _assert_live_ready(settings: Settings) -> None:
    if not settings.enable_live:
        raise LiveIngestionDisabled("sportmonks")
    if not settings.sportmonks_key:
        raise ProviderNotConfigured("sportmonks")
    if settings.data_mode != "live":
        raise RuntimeError(
            "Live Sportmonks ingestion requires PREDICTA_INGESTION_DATA_MODE=live "
            "and PREDICTA_INGESTION_ENABLE_LIVE=true. It never falls back to mock data."
        )


def _build_pipeline(settings: Settings, clock: Clock, *, dry_run: bool) -> IngestionPipeline:
    raw_store = FilesystemRawStore(Path(settings.raw_store_path))
    sink: MemoryCanonicalSink | SqlCanonicalSink
    if dry_run:
        sink = MemoryCanonicalSink()
    else:
        engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        sink = SqlCanonicalSink(clock=clock, engine=engine)
    return IngestionPipeline(
        settings=settings,
        clock=clock,
        raw_store=raw_store,
        sink=sink,
        resolver=IdentityResolver(clock),
        dry_run=dry_run,
    )


def _parse_date(value: str, *, end_of_day: bool) -> datetime:
    if "T" in value:
        return parse_rfc3339(value)
    parsed = datetime.fromisoformat(f"{value}T23:59:59" if end_of_day else f"{value}T00:00:00")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _report_payload(report: IngestionReport) -> dict[str, object]:
    return {
        "provider": report.provider,
        "resource": report.resource.value,
        "data_mode": report.data_mode.value,
        "dry_run": report.dry_run,
        "records_read": report.records_read,
        "records_accepted": report.records_accepted,
        "duplicates": report.duplicates,
        "quarantined": [item.reason_code for item in report.quarantined],
    }


if __name__ == "__main__":
    raise SystemExit(main())
