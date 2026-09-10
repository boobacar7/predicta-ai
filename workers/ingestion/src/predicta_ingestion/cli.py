from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine

from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.config import Settings, get_settings, load_local_env
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.history import HistoryIngestReport, ingest_history, memory_sink
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.ids import stable_entity_id
from predicta_ingestion.ml.dataset import MlDataset, build_ml_dataset
from predicta_ingestion.persistence.memory import MemoryCanonicalSink, TeeCanonicalSink
from predicta_ingestion.persistence.sql import SqlCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline, IngestionReport
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.errors import LiveIngestionDisabled, ProviderError, ProviderNotConfigured
from predicta_ingestion.providers.http import HttpxTransport
from predicta_ingestion.providers.leagues import V1_FOOTBALL_LEAGUES
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.sportmonks import SportmonksFootballProvider
from predicta_ingestion.raw.store import FilesystemRawStore
from predicta_ingestion.secrets import redact_text

_LEAGUE_HELP = ", ".join(item.slug for item in V1_FOOTBALL_LEAGUES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m predicta_ingestion",
        description="PREDICTA football ingestion. Live Sportmonks is opt-in and never falls back to mock.",
    )
    sub = parser.add_subparsers(dest="command")
    ingest = sub.add_parser("ingest-football", help="Ingest V1 football leagues and fixtures from Sportmonks.")
    _add_common_ingest_args(ingest, default_league="all")
    history = sub.add_parser("ingest-history", help="Discover Sportmonks seasons and ingest historical fixtures.")
    _add_common_ingest_args(history, default_league="mls")
    history.add_argument("--season", help="Sportmonks season id or season name as returned by the provider.")
    history.add_argument(
        "--all-seasons",
        action="store_true",
        help="Ingest every discovered season. Default for MLS; European V1 is capped unless this flag is set.",
    )
    history.add_argument("--write-dataset", dest="write_dataset", help="Write the PIT 1X2 dataset JSON after ingest.")
    dataset = sub.add_parser(
        "build-ml-dataset",
        help="Ingest history (if needed) and emit a point-in-time 1X2 dataset.",
    )
    _add_common_ingest_args(dataset, default_league="mls")
    dataset.add_argument("--season", help="Sportmonks season id or season name as returned by the provider.")
    dataset.add_argument("--all-seasons", action="store_true")
    dataset.add_argument("--write-dataset", dest="write_dataset", help="Output path for the dataset JSON.")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    load_local_env()
    try:
        settings = get_settings()
        payload = _dispatch(args, settings)
    except (
        LiveIngestionDisabled,
        ProviderNotConfigured,
        ProviderError,
        RuntimeError,
        TypeError,
        ValidationError,
    ) as exc:
        print(_redact_cli(str(exc)), file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _add_common_ingest_args(parser: argparse.ArgumentParser, *, default_league: str) -> None:
    parser.add_argument("--league", default=default_league, help=f"League slug, alias (MLS), or 'all'. {_LEAGUE_HELP}")
    parser.add_argument("--date-from", dest="date_from", help="UTC start date YYYY-MM-DD (inclusive).")
    parser.add_argument("--date-to", dest="date_to", help="UTC end date YYYY-MM-DD (inclusive).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch, validate and normalize without writing PostgreSQL or the raw store.",
    )


def _dispatch(args: argparse.Namespace, settings: Settings) -> dict[str, object]:
    if args.command == "ingest-football":
        report = ingest_football(
            settings=settings,
            league=args.league,
            date_from=args.date_from,
            date_to=args.date_to,
            dry_run=args.dry_run,
        )
        return _report_payload(report)
    if args.command in {"ingest-history", "build-ml-dataset"}:
        history, dataset = run_history(
            settings=settings,
            league=args.league,
            season=getattr(args, "season", None),
            date_from=args.date_from,
            date_to=args.date_to,
            all_seasons=bool(getattr(args, "all_seasons", False)),
            dry_run=args.dry_run,
            build_dataset=args.command == "build-ml-dataset" or bool(getattr(args, "write_dataset", None)),
        )
        payload: dict[str, object] = history.to_dict()
        if dataset is not None:
            payload["dataset"] = {
                "dataset_version": dataset.dataset_version,
                "cutoff_policy": dataset.cutoff_policy,
                "observation_count": len(dataset.observations),
                "standings_available": dataset.standings_available,
                "seasons": dataset.seasons,
            }
            output = getattr(args, "write_dataset", None)
            if output:
                Path(output).write_text(json.dumps(dataset.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
                payload["dataset_path"] = output
        return payload
    raise RuntimeError(f"Unknown command '{args.command}'.")


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
    sportmonks = provider or _sportmonks_provider(settings, clock)
    active_pipeline = pipeline or _build_pipeline(settings, clock, dry_run=dry_run, history=False)
    request = ProviderRequest(
        resource=ResourceType.FIXTURES,
        sport=SportCode.FOOTBALL,
        league=league,
        since=_parse_date(date_from, end_of_day=False) if date_from else None,
        until=_parse_date(date_to, end_of_day=True) if date_to else None,
    )
    report = active_pipeline.run(sportmonks, request)
    _record_run(active_pipeline, clock, report, dry_run=dry_run)
    return report


def run_history(
    *,
    settings: Settings,
    league: str = "mls",
    season: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    all_seasons: bool = False,
    dry_run: bool = False,
    build_dataset: bool = False,
    provider: SportmonksFootballProvider | None = None,
    pipeline: IngestionPipeline | None = None,
    clock: Clock | None = None,
) -> tuple[HistoryIngestReport, MlDataset | None]:
    _assert_live_ready(settings)
    active_clock = clock or Clock()
    sportmonks = provider or _sportmonks_provider(settings, active_clock)
    active_pipeline = pipeline or _build_pipeline(settings, active_clock, dry_run=dry_run, history=True)
    history = ingest_history(
        provider=sportmonks,
        pipeline=active_pipeline,
        clock=active_clock,
        league=league,
        season=season,
        date_from=_parse_date(date_from, end_of_day=False) if date_from else None,
        date_to=_parse_date(date_to, end_of_day=True) if date_to else None,
        all_seasons=all_seasons,
    )
    dataset: MlDataset | None = None
    if build_dataset:
        dataset = build_ml_dataset(
            PointInTimeStore(memory_sink(active_pipeline)),
            competition=None if league in {None, "", "all"} else league,
            seasons=None if all_seasons or not season else [item.season for item in history.seasons],
        )
    return history, dataset


def _sportmonks_provider(settings: Settings, clock: Clock) -> SportmonksFootballProvider:
    return SportmonksFootballProvider(
        enable_live=settings.enable_live,
        api_token=settings.sportmonks_key,
        clock=clock,
        transport=HttpxTransport(),
        base_url=settings.sportmonks_base_url,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
    )


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


def _build_pipeline(settings: Settings, clock: Clock, *, dry_run: bool, history: bool) -> IngestionPipeline:
    raw_store = FilesystemRawStore(Path(settings.raw_store_path))
    memory = MemoryCanonicalSink()
    sink: MemoryCanonicalSink | SqlCanonicalSink | TeeCanonicalSink
    if dry_run:
        sink = memory
    elif history:
        engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        sink = TeeCanonicalSink(memory, SqlCanonicalSink(clock=clock, engine=engine))
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


def _record_run(pipeline: IngestionPipeline, clock: Clock, report: IngestionReport, *, dry_run: bool) -> None:
    if dry_run:
        return
    recorder = getattr(pipeline._sink, "record_run", None)
    if not callable(recorder):
        return
    recorder(
        run_id=stable_entity_id("run", "sportmonks", clock.now().isoformat()),
        provider="sportmonks",
        resource_type=ResourceType.FIXTURES.value,
        status="completed" if not report.quarantined else "completed_with_quarantine",
        data_mode=report.data_mode.value,
        records_read=report.records_read,
        records_accepted=report.records_accepted,
        records_quarantined=len(report.quarantined),
    )


def _parse_date(value: str, *, end_of_day: bool) -> datetime:
    if "T" in value:
        return parse_rfc3339(value)
    parsed = datetime.fromisoformat(f"{value}T23:59:59" if end_of_day else f"{value}T00:00:00")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _redact_cli(message: str) -> str:
    secret = (
        os.environ.get("SPORTMONKS_API_TOKEN") or os.environ.get("PREDICTA_INGESTION_SPORTMONKS_KEY") or ""
    ).strip()
    return redact_text(message, secret or None)


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
