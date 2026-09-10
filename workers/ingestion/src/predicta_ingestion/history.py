from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.canonical.models import Match
from predicta_ingestion.clock import Clock
from predicta_ingestion.identity.resolver import IdentityDiagnostic
from predicta_ingestion.ids import stable_entity_id
from predicta_ingestion.persistence.memory import MemoryCanonicalSink, TeeCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.leagues import V1FootballLeague, resolve_v1_leagues
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.seasons import DiscoveredSeason, parse_discovered_seasons, select_seasons
from predicta_ingestion.providers.sportmonks import SportmonksFootballProvider
from predicta_ingestion.quality.history import SeasonQualityReport, build_season_quality_report
from predicta_ingestion.raw.envelope import RawEnvelope


@dataclass
class HistoryIngestReport:
    ingestion_run_id: str
    provider: str
    data_mode: str
    dry_run: bool
    discovered: list[dict[str, object]] = field(default_factory=list)
    seasons: list[SeasonQualityReport] = field(default_factory=list)
    identity: list[IdentityDiagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        identity_rows = [item.to_dict() for item in self.identity]
        methods: dict[str, int] = {}
        quarantined_identity = 0
        for item in self.identity:
            if item.status == "quarantined":
                quarantined_identity += 1
                continue
            method = item.resolution_method or "unknown"
            methods[method] = methods.get(method, 0) + 1
        return {
            "ingestion_run_id": self.ingestion_run_id,
            "provider": self.provider,
            "data_mode": self.data_mode,
            "dry_run": self.dry_run,
            "discovered": self.discovered,
            "seasons": [item.to_dict() for item in self.seasons],
            "identity": identity_rows,
            "identity_summary": {
                "resolved_by_method": methods,
                "quarantined_count": quarantined_identity,
            },
            "totals": {
                "fetched_count": sum(item.fetched_count for item in self.seasons),
                "normalized_count": sum(item.normalized_count for item in self.seasons),
                "inserted_count": sum(item.inserted_count for item in self.seasons),
                "duplicate_count": sum(item.duplicate_count for item in self.seasons),
                "quarantined_count": sum(item.quarantined_count for item in self.seasons),
            },
        }


def ingest_history(
    *,
    provider: SportmonksFootballProvider,
    pipeline: IngestionPipeline,
    clock: Clock,
    league: str = "mls",
    season: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    all_seasons: bool = False,
) -> HistoryIngestReport:
    run_id = stable_entity_id("run", "sportmonks-history", clock.now().isoformat())
    leagues = resolve_v1_leagues(league)
    sink = memory_sink(pipeline)
    report = HistoryIngestReport(
        ingestion_run_id=run_id,
        provider=provider.name,
        data_mode=pipeline._settings.resolved_data_mode(),
        dry_run=pipeline._dry_run,
    )
    from_date = date_from.date() if date_from else None
    to_date = date_to.date() if date_to else None
    for item in leagues:
        discovered = _discover_seasons(provider, pipeline, item)
        selected = select_seasons(
            discovered,
            league=item,
            season=season,
            date_from=from_date,
            date_to=to_date,
            all_seasons=all_seasons,
        )
        for found in discovered:
            report.discovered.append(
                {
                    "competition": item.name,
                    "league_slug": item.slug,
                    "season_id": found.provider_id,
                    "season": found.name,
                    "starting_at": found.starting_at.isoformat() if found.starting_at else None,
                    "ending_at": found.ending_at.isoformat() if found.ending_at else None,
                    "selected": found.provider_id in {row.provider_id for row in selected},
                }
            )
        for selected_season in selected:
            report.seasons.append(
                _ingest_season(
                    provider=provider,
                    pipeline=pipeline,
                    sink=sink,
                    league=item,
                    discovered=selected_season,
                    date_from=date_from,
                    date_to=date_to,
                    run_id=run_id,
                )
            )
    recorder = getattr(pipeline._sink, "record_run", None)
    if callable(recorder) and not pipeline._dry_run:
        has_quarantine = any(item.quarantined_count for item in report.seasons)
        recorder(
            run_id=run_id,
            provider="sportmonks",
            resource_type=ResourceType.FIXTURES.value,
            status="completed_with_quarantine" if has_quarantine else "completed",
            data_mode=report.data_mode,
            records_read=sum(item.fetched_count for item in report.seasons),
            records_accepted=sum(item.inserted_count for item in report.seasons),
            records_quarantined=sum(item.quarantined_count for item in report.seasons),
        )
    report.identity = pipeline._resolver.identity_report()
    return report


def memory_sink(pipeline: IngestionPipeline) -> MemoryCanonicalSink:
    sink = pipeline._sink
    if isinstance(sink, MemoryCanonicalSink):
        return sink
    if isinstance(sink, TeeCanonicalSink):
        return sink.memory
    raise TypeError("History ingest requires a MemoryCanonicalSink or TeeCanonicalSink for PIT reads.")


def count_fixtures(envelopes: list[RawEnvelope]) -> int:
    total = 0
    for envelope in envelopes:
        if envelope.resource is not ResourceType.FIXTURES:
            continue
        payload = json.loads(envelope.body.decode("utf-8"))
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, list):
            total += len(data)
        elif isinstance(data, dict) and data.get("id") is not None:
            total += 1
    return total


def _discover_seasons(
    provider: SportmonksFootballProvider,
    pipeline: IngestionPipeline,
    league: V1FootballLeague,
) -> list[DiscoveredSeason]:
    envelopes = provider.fetch(
        ProviderRequest(resource=ResourceType.SEASONS, sport=SportCode.FOOTBALL, league=league.slug)
    )
    pipeline.ingest_envelopes(provider.name, ResourceType.SEASONS, envelopes)
    discovered: list[DiscoveredSeason] = []
    for envelope in envelopes:
        payload = json.loads(envelope.body.decode("utf-8"))
        if isinstance(payload, dict):
            discovered.extend(parse_discovered_seasons(payload, league))
    return discovered


def _ingest_season(
    *,
    provider: SportmonksFootballProvider,
    pipeline: IngestionPipeline,
    sink: MemoryCanonicalSink,
    league: V1FootballLeague,
    discovered: DiscoveredSeason,
    date_from: datetime | None,
    date_to: datetime | None,
    run_id: str,
) -> SeasonQualityReport:
    before_ids = set(sink.matches)
    envelopes = provider.fetch(
        ProviderRequest(
            resource=ResourceType.FIXTURES,
            sport=SportCode.FOOTBALL,
            league=league.slug,
            season=discovered.provider_id,
            since=date_from,
            until=date_to,
        )
    )
    fetched = count_fixtures(envelopes)
    ingest = pipeline.ingest_envelopes(
        provider.name,
        ResourceType.FIXTURES,
        envelopes,
        since=date_from,
        until=date_to,
    )
    season_matches = [
        match
        for match in sink.matches.values()
        if _match_in_season(match, sink, discovered, league)
        and _within_dates(match, date_from, date_to)
    ]
    after_ids = {item.id for item in season_matches}
    inserted = after_ids - before_ids
    duplicate = after_ids & before_ids
    if ingest.duplicates and not inserted:
        duplicate = after_ids
    return build_season_quality_report(
        competition=league.name,
        season=discovered.name,
        season_id=discovered.provider_id,
        fetched_count=fetched,
        matches=season_matches,
        inserted_ids=inserted,
        duplicate_ids=duplicate,
        quarantined=ingest.quarantined,
        provider=provider.name,
        data_mode=ingest.data_mode,
        ingestion_run_id=run_id,
    )


def _match_in_season(
    match: Match,
    sink: MemoryCanonicalSink,
    discovered: DiscoveredSeason,
    league: V1FootballLeague,
) -> bool:
    canonical = sink.leagues.get(match.league_id)
    if canonical is None:
        return False
    return canonical.season == discovered.name and canonical.name == league.name


def _within_dates(match: Match, date_from: datetime | None, date_to: datetime | None) -> bool:
    if date_from is not None and match.kickoff_at < date_from:
        return False
    if date_to is not None and match.kickoff_at > date_to:
        return False
    return True
