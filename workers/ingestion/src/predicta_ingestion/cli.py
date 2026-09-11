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
from predicta_ingestion.ml.export import write_dataset_artifacts
from predicta_ingestion.ml.quality import build_quality_report
from predicta_ingestion.persistence.load import hydrate_match_keys_from_sql, hydrate_resolver_from_sql, load_memory_sink
from predicta_ingestion.persistence.memory import MemoryCanonicalSink, TeeCanonicalSink
from predicta_ingestion.persistence.sql import SqlCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline, IngestionReport
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.errors import LiveIngestionDisabled, ProviderError, ProviderNotConfigured
from predicta_ingestion.providers.http import HttpxTransport
from predicta_ingestion.providers.leagues import V1_FOOTBALL_LEAGUES
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.sportmonks import SportmonksFootballProvider
from predicta_ingestion.providers.the_odds_api import TheOddsApiProvider
from predicta_ingestion.raw.store import FilesystemRawStore
from predicta_ingestion.secrets import redact_text

_LEAGUE_HELP = ", ".join(item.slug for item in V1_FOOTBALL_LEAGUES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m predicta_ingestion",
        description=(
            "PREDICTA football ingestion. Live Sportmonks and The Odds API are opt-in and never fall back to mock."
        ),
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
    odds = sub.add_parser("ingest-odds", help="Ingest football 1X2 odds from The Odds API.")
    _add_common_ingest_args(odds, default_league="all")
    odds.add_argument(
        "--as-of",
        dest="as_of",
        help="UTC RFC 3339 timestamp for the historical odds snapshot. Omit for current pre-match odds.",
    )
    dataset = sub.add_parser(
        "build-ml-dataset",
        help="Build a point-in-time 1X2 dataset from ingested PostgreSQL rows. Does not train a model.",
    )
    dataset.add_argument("--league", default="all", help=f"League slug, alias (MLS), or 'all'. {_LEAGUE_HELP}")
    dataset.add_argument(
        "--season",
        help="Limit labeled rows to this season name (Elo/form still use earlier PIT facts).",
    )
    dataset.add_argument(
        "--write-dataset",
        dest="write_dataset",
        default="./var/football-1x2-history.json",
        help="Output JSON path. Parquet and quality sidecar files use the same stem.",
    )
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
    if args.command == "ingest-odds":
        report = ingest_odds(
            settings=settings,
            league=args.league,
            date_from=args.date_from,
            date_to=args.date_to,
            as_of=getattr(args, "as_of", None),
            dry_run=args.dry_run,
        )
        return _report_payload(report)
    if args.command == "ingest-history":
        history, dataset = run_history(
            settings=settings,
            league=args.league,
            season=getattr(args, "season", None),
            date_from=args.date_from,
            date_to=args.date_to,
            all_seasons=bool(getattr(args, "all_seasons", False)),
            dry_run=args.dry_run,
            build_dataset=bool(getattr(args, "write_dataset", None)),
        )
        payload: dict[str, object] = history.to_dict()
        if dataset is not None:
            payload["dataset"] = _dataset_summary(dataset)
            output = getattr(args, "write_dataset", None)
            if output:
                payload["dataset_paths"] = write_dataset_artifacts(dataset, output)
        return payload
    if args.command == "build-ml-dataset":
        store = _sql_store(settings)
        dataset = build_ml_dataset(
            store,
            competition=None if args.league in {None, "", "all"} else args.league,
            seasons=None if not getattr(args, "season", None) else [args.season],
        )
        payload = _dataset_summary(dataset)
        payload["dataset_paths"] = write_dataset_artifacts(dataset, args.write_dataset, store=store)
        payload["quality"] = build_quality_report(dataset, store=store)
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


def ingest_odds(
    *,
    settings: Settings,
    league: str = "all",
    date_from: str | None = None,
    date_to: str | None = None,
    as_of: str | None = None,
    dry_run: bool = False,
    provider: TheOddsApiProvider | None = None,
    pipeline: IngestionPipeline | None = None,
) -> IngestionReport:
    _assert_odds_ready(settings)
    clock = Clock()
    odds_provider = provider or _odds_provider(settings, clock)
    active_pipeline = pipeline or _build_pipeline(settings, clock, dry_run=dry_run, history=False, odds=True)
    request = ProviderRequest(
        resource=ResourceType.ODDS,
        sport=SportCode.FOOTBALL,
        league=league,
        since=_parse_date(date_from, end_of_day=False) if date_from else None,
        until=_parse_date(date_to, end_of_day=True) if date_to else None,
        as_of=parse_rfc3339(as_of) if as_of else None,
    )
    report = active_pipeline.run(odds_provider, request)
    _record_run(
        active_pipeline,
        clock,
        report,
        dry_run=dry_run,
        provider_name="the_odds_api",
        resource=ResourceType.ODDS,
    )
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


def build_dataset_from_sql(
    *,
    settings: Settings,
    league: str = "all",
    season: str | None = None,
) -> MlDataset:
    store = _sql_store(settings)
    seasons = None if not season else [season]
    return build_ml_dataset(
        store,
        competition=None if league in {None, "", "all"} else league,
        seasons=seasons,
    )


def _sql_store(settings: Settings) -> PointInTimeStore:
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    sink = load_memory_sink(engine)
    if not sink.matches:
        raise RuntimeError("No ingested matches in PostgreSQL. Run ingest-history before building the dataset.")
    return PointInTimeStore(sink)


def _dataset_summary(dataset: MlDataset) -> dict[str, object]:
    reasons: dict[str, int] = {}
    for item in dataset.rejections:
        reasons[item.reason] = reasons.get(item.reason, 0) + 1
    return {
        "dataset_version": dataset.dataset_version,
        "feature_schema_version": dataset.feature_schema_version,
        "code_version": dataset.code_version,
        "cutoff_policy": dataset.cutoff_policy,
        "source": dataset.source,
        "generated_at": dataset.generated_at.isoformat(),
        "observation_count": dataset.observation_count,
        "rejected_count": dataset.rejected_count,
        "rejection_reasons": reasons,
        "feature_count": len(dataset.feature_schema),
        "standings_available": dataset.standings_available,
        "competitions": dataset.competitions,
        "seasons": dataset.seasons,
        "period_start": dataset.period_start.isoformat() if dataset.period_start else None,
        "period_end": dataset.period_end.isoformat() if dataset.period_end else None,
    }


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


def _odds_provider(settings: Settings, clock: Clock) -> TheOddsApiProvider:
    return TheOddsApiProvider(
        enable_live=settings.enable_live,
        api_key=settings.the_odds_api_key,
        clock=clock,
        transport=HttpxTransport(),
        base_url=settings.the_odds_api_base_url,
        timeout_seconds=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
        regions=settings.the_odds_api_regions,
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


def _assert_odds_ready(settings: Settings) -> None:
    if not settings.enable_live:
        raise LiveIngestionDisabled("the_odds_api")
    if not settings.the_odds_api_key:
        raise ProviderNotConfigured("the_odds_api")
    if settings.data_mode != "live":
        raise RuntimeError(
            "Live The Odds API ingestion requires PREDICTA_INGESTION_DATA_MODE=live "
            "and PREDICTA_INGESTION_ENABLE_LIVE=true. It never falls back to mock data."
        )


def _build_pipeline(
    settings: Settings,
    clock: Clock,
    *,
    dry_run: bool,
    history: bool,
    odds: bool = False,
) -> IngestionPipeline:
    raw_store = FilesystemRawStore(Path(settings.raw_store_path))
    memory = MemoryCanonicalSink()
    resolver = IdentityResolver(clock)
    sink: MemoryCanonicalSink | SqlCanonicalSink | TeeCanonicalSink
    if dry_run:
        sink = memory
    elif history:
        engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        hydrate_resolver_from_sql(resolver, engine)
        sink = TeeCanonicalSink(memory, SqlCanonicalSink(clock=clock, engine=engine))
    else:
        engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        hydrate_resolver_from_sql(resolver, engine)
        if odds:
            hydrate_match_keys_from_sql(resolver, engine)
        sink = SqlCanonicalSink(clock=clock, engine=engine)
    return IngestionPipeline(
        settings=settings,
        clock=clock,
        raw_store=raw_store,
        sink=sink,
        resolver=resolver,
        dry_run=dry_run,
    )


def _record_run(
    pipeline: IngestionPipeline,
    clock: Clock,
    report: IngestionReport,
    *,
    dry_run: bool,
    provider_name: str = "sportmonks",
    resource: ResourceType = ResourceType.FIXTURES,
) -> None:
    if dry_run:
        return
    recorder = getattr(pipeline._sink, "record_run", None)
    if not callable(recorder):
        return
    recorder(
        run_id=stable_entity_id("run", provider_name, clock.now().isoformat()),
        provider=provider_name,
        resource_type=resource.value,
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
    sportmonks = (
        os.environ.get("SPORTMONKS_API_TOKEN") or os.environ.get("PREDICTA_INGESTION_SPORTMONKS_KEY") or ""
    ).strip()
    odds_key = (
        os.environ.get("THE_ODDS_API_KEY") or os.environ.get("PREDICTA_INGESTION_THE_ODDS_API_KEY") or ""
    ).strip()
    redacted = redact_text(message, sportmonks or None)
    return redact_text(redacted, odds_key or None)


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
