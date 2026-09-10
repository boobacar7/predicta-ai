from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from predicta_ingestion.canonical.enums import DataMode, ResourceType
from predicta_ingestion.canonical.models import CanonicalBatch
from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.identity.resolver import IdentityResolver
from predicta_ingestion.ids import canonical_id
from predicta_ingestion.normalization.basketball import BasketballNormalizer
from predicta_ingestion.normalization.football import FootballNormalizer
from predicta_ingestion.normalization.odds import OddsNormalizer
from predicta_ingestion.normalization.sportmonks import SportmonksFootballNormalizer
from predicta_ingestion.normalization.tennis import TennisNormalizer
from predicta_ingestion.persistence.memory import CanonicalSink, MemoryCanonicalSink, PersistResult
from predicta_ingestion.providers.protocols import ProviderRequest, SportsProvider
from predicta_ingestion.quality.quarantine import QuarantineItem
from predicta_ingestion.raw.store import FilesystemRawStore, RawStore, StoredRaw
from predicta_ingestion.validation.validator import Validator


@dataclass
class IngestionReport:
    provider: str
    resource: ResourceType
    data_mode: DataMode
    records_read: int = 0
    records_accepted: int = 0
    duplicates: int = 0
    quarantined: list[QuarantineItem] = field(default_factory=list)
    persist: PersistResult | None = None
    dry_run: bool = False


class IngestionPipeline:
    def __init__(
        self,
        *,
        settings: Settings,
        clock: Clock,
        raw_store: RawStore,
        sink: CanonicalSink,
        resolver: IdentityResolver,
        dry_run: bool = False,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._raw_store = raw_store
        self._sink = sink
        self._resolver = resolver
        self._dry_run = dry_run
        self._validator = Validator(settings)
        self._football = FootballNormalizer(clock)
        self._sportmonks = SportmonksFootballNormalizer(clock)
        self._basketball = BasketballNormalizer(clock)
        self._tennis = TennisNormalizer(clock)
        self._odds = OddsNormalizer(clock)

    def run(self, provider: SportsProvider, request: ProviderRequest) -> IngestionReport:
        expected_mode = DataMode(self._settings.resolved_data_mode())
        report = IngestionReport(
            provider=provider.name,
            resource=request.resource,
            data_mode=expected_mode,
            dry_run=self._dry_run,
        )
        envelopes = provider.fetch(request)
        report.records_read = len(envelopes)
        for envelope in envelopes:
            if self._dry_run:
                stored = StoredRaw(
                    raw_id=canonical_id("raw", envelope.provider, envelope.resource, envelope.checksum_sha256[:12]),
                    envelope=envelope,
                    storage_uri="dry-run",
                    duplicate=False,
                )
            else:
                stored = self._raw_store.put(envelope)
                if stored.duplicate:
                    report.duplicates += 1
                    continue
            try:
                payload = self._validator.validate(stored, expected_mode=expected_mode)
                batch = self._normalize(stored, payload)
                quarantined = self._resolver.resolve(batch, data_mode=expected_mode)
                report.quarantined.extend(quarantined)
                if self._dry_run:
                    persist = PersistResult(
                        inserted=len(batch.sports)
                        + len(batch.leagues)
                        + len(batch.teams)
                        + len(batch.matches)
                    )
                else:
                    self._sink.record_raw(stored)
                    persist = self._sink.persist(batch)
                    self._sink.persist_identity(self._resolver.bindings())
                report.records_accepted += persist.inserted
                report.duplicates += persist.duplicates
                report.persist = persist
            except ValidationError as exc:
                item = QuarantineItem(
                    reason_code=exc.reason_code,
                    detail=exc.detail,
                    provider=provider.name,
                    entity_type=request.resource.value,
                    data_mode=expected_mode,
                    raw_payload_id=stored.id,
                    created_at=self._clock.now(),
                )
                report.quarantined.append(item)
        return report

    def _normalize(self, stored: Any, payload: dict[str, Any]) -> CanonicalBatch:
        provider = stored.envelope.provider
        if provider in {"sportmonks", "sportmonks.football"}:
            return self._sportmonks.normalize(stored, payload)
        if provider.endswith("api_football") or provider == "mock.api_football":
            return self._football.normalize(stored, payload)
        if "balldontlie" in provider:
            return self._basketball.normalize(stored, payload)
        if "tennis" in provider:
            return self._tennis.normalize(stored, payload)
        if "odds" in provider:
            return self._odds.normalize(stored, payload)
        raise ValidationError("unknown_provider", f"No normalizer registered for {provider}.")


def build_default_pipeline(settings: Settings, clock: Clock, raw_root: Any | None = None) -> IngestionPipeline:
    return IngestionPipeline(
        settings=settings,
        clock=clock,
        raw_store=FilesystemRawStore(raw_root or settings.raw_store_path),
        sink=MemoryCanonicalSink(),
        resolver=IdentityResolver(clock),
    )
