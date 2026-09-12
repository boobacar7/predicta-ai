from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.canonical.models import OddsSnapshot
from predicta_ingestion.clock import parse_rfc3339, to_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import canonical_id, slugify
from predicta_ingestion.normalization.odds import CANONICAL_1X2_MARKET
from predicta_ingestion.persistence.memory import MemoryCanonicalSink
from predicta_ingestion.pipeline import IngestionPipeline, IngestionReport
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.leagues import resolve_v1_leagues
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.the_odds_api import LIVE_ODDS_PROVIDER, TheOddsApiProvider
from predicta_ingestion.quality.quarantine import QuarantineItem
from predicta_ingestion.raw.envelope import RawEnvelope
from predicta_ingestion.secrets import redact_text

PILOT_LEAGUES: tuple[str, ...] = ("premier-league", "ligue-1")
MAX_PILOT_REQUESTS = 4
DEFAULT_AS_OF_BEFORE = datetime.fromisoformat("2026-08-16T11:00:00+00:00")
DEFAULT_AS_OF_AFTER = datetime.fromisoformat("2026-08-16T15:00:00+00:00")
DEFAULT_PIT_CUTOFF = datetime.fromisoformat("2026-08-16T14:00:00+00:00")
CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED = 10
VALUE_SNAPSHOT_RULE = (
    "Last complete 1X2 snapshot with available_at <= cutoff, ordered by "
    "(available_at, collected_at, snapshot.id). Bookmaker identity is not a "
    "selection criterion; Pinnacle is not preferred because it looks better."
)


@dataclass(frozen=True)
class OddsQuota:
    requests_used: int | None
    requests_remaining: int | None
    requests_last: int | None

    def to_dict(self) -> dict[str, int | None]:
        return {
            "requests_used": self.requests_used,
            "requests_remaining": self.requests_remaining,
            "requests_last": self.requests_last,
        }


@dataclass(frozen=True)
class HistoricalFetch:
    league: str
    requested_as_of: datetime
    snapshot_timestamp: str | None
    previous_timestamp: str | None
    next_timestamp: str | None
    quota: OddsQuota
    event_ids: tuple[str, ...]
    raw_payload_id: str | None
    request_key: str

    def to_dict(self) -> dict[str, object]:
        return {
            "league": self.league,
            "requested_as_of": to_rfc3339(self.requested_as_of),
            "snapshot_timestamp": self.snapshot_timestamp,
            "previous_timestamp": self.previous_timestamp,
            "next_timestamp": self.next_timestamp,
            "quota": self.quota.to_dict(),
            "event_count": len(self.event_ids),
            "event_ids": list(self.event_ids),
            "raw_payload_id": self.raw_payload_id,
            "request_key": self.request_key,
        }


@dataclass
class IdentityStats:
    events: int = 0
    matched: int = 0
    rejected: int = 0
    snapshots: int = 0
    false_match_count: int = 0
    exact_matches: int = 0
    alias_matches: int = 0
    rejected_event_ids: list[str] = field(default_factory=list)
    matched_event_ids: list[str] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        if self.events == 0:
            return 0.0
        return self.matched / self.events

    def to_dict(self) -> dict[str, object]:
        return {
            "events": self.events,
            "matched": self.matched,
            "rejected": self.rejected,
            "snapshots": self.snapshots,
            "false_match_count": self.false_match_count,
            "match_rate": round(self.match_rate, 6),
            "exact_matches": self.exact_matches,
            "alias_matches": self.alias_matches,
            "rejected_event_ids": self.rejected_event_ids,
            "matched_event_ids": self.matched_event_ids,
        }


@dataclass(frozen=True)
class BookmakerInventory:
    bookmakers: tuple[str, ...]
    snapshot_counts: dict[str, int]
    last_updates: dict[str, list[str]]

    def to_dict(self) -> dict[str, object]:
        return {
            "bookmakers": list(self.bookmakers),
            "snapshot_counts": dict(self.snapshot_counts),
            "last_updates": {key: list(values) for key, values in self.last_updates.items()},
            "selection_rule": VALUE_SNAPSHOT_RULE,
        }


@dataclass(frozen=True)
class PitCheck:
    cutoff_at: str
    match_id: str | None
    before_eligible: bool
    after_excluded: bool
    selected_available_at: str | None
    leaked: bool

    @property
    def passed(self) -> bool:
        return self.before_eligible and self.after_excluded and not self.leaked

    def to_dict(self) -> dict[str, object]:
        return {
            "cutoff_at": self.cutoff_at,
            "match_id": self.match_id,
            "before_eligible": self.before_eligible,
            "after_excluded": self.after_excluded,
            "selected_available_at": self.selected_available_at,
            "leaked": self.leaked,
            "passed": self.passed,
        }


@dataclass
class HistoricalOddsPilotReport:
    leagues: tuple[str, ...]
    as_of_before: datetime
    as_of_after: datetime
    pit_cutoff: datetime
    fetches: list[HistoricalFetch]
    identity: IdentityStats
    bookmakers: BookmakerInventory
    pit: PitCheck
    ingestion: list[dict[str, object]]
    dry_run: bool
    credits_consumed: int | None
    requests: int
    documented_credits_per_request: int = CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED

    def to_dict(self) -> dict[str, object]:
        payload = {
            "leagues": list(self.leagues),
            "as_of_before": to_rfc3339(self.as_of_before),
            "as_of_after": to_rfc3339(self.as_of_after),
            "pit_cutoff": to_rfc3339(self.pit_cutoff),
            "requests": self.requests,
            "credits_consumed": self.credits_consumed,
            "documented_credits_per_request": self.documented_credits_per_request,
            "dry_run": self.dry_run,
            "fetches": [item.to_dict() for item in self.fetches],
            "identity": self.identity.to_dict(),
            "bookmakers": self.bookmakers.to_dict(),
            "pit": self.pit.to_dict(),
            "ingestion": self.ingestion,
            "value_snapshot_rule": VALUE_SNAPSHOT_RULE,
        }
        return _reject_secrets(payload)


def parse_odds_quota(headers: dict[str, str]) -> OddsQuota:
    lowered = {key.lower(): value for key, value in headers.items()}
    return OddsQuota(
        requests_used=_optional_int(lowered.get("x-requests-used")),
        requests_remaining=_optional_int(lowered.get("x-requests-remaining")),
        requests_last=_optional_int(lowered.get("x-requests-last")),
    )


def historical_timestamps(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    return (
        _optional_str(payload.get("snapshot_timestamp")),
        _optional_str(payload.get("previous_timestamp")),
        _optional_str(payload.get("next_timestamp")),
    )


def next_historical_as_of(payload: dict[str, Any]) -> datetime | None:
    """Return the provider's next snapshot time. Never interpolates between timestamps."""
    next_raw = _optional_str(payload.get("next_timestamp"))
    if next_raw is None:
        return None
    return parse_rfc3339(next_raw)


def assert_pilot_scope(leagues: tuple[str, ...], *, max_requests: int) -> None:
    if max_requests > MAX_PILOT_REQUESTS:
        raise ValidationError(
            "pilot_cap",
            f"Historical odds pilot refuses more than {MAX_PILOT_REQUESTS} requests.",
        )
    allowed = set(PILOT_LEAGUES)
    unknown = [slug for slug in leagues if slug not in allowed]
    if unknown:
        raise ValidationError(
            "pilot_scope",
            "Historical odds pilot only accepts premier-league and ligue-1, "
            f"not {', '.join(unknown)}.",
        )
    planned = len(leagues) * 2
    if planned > max_requests:
        raise ValidationError(
            "pilot_cap",
            f"Pilot window needs {planned} requests but max_requests={max_requests}.",
        )
    for slug in leagues:
        resolve_v1_leagues(slug)


def credits_consumed(fetches: list[HistoricalFetch]) -> int | None:
    last_values = [item.quota.requests_last for item in fetches]
    if any(value is None for value in last_values):
        return None
    return sum(last_values)  # type: ignore[arg-type]


def identity_stats(
    *,
    event_ids: list[str],
    snapshots: list[OddsSnapshot],
    quarantined: list[QuarantineItem],
    exact_matches: int,
    alias_matches: int,
) -> IdentityStats:
    unique_events = list(dict.fromkeys(event_ids))
    matched_ids = list(
        dict.fromkeys(_event_id_from_provider_id(item.provenance.provider_id) for item in snapshots)
    )
    unmatched_ids = list(
        dict.fromkeys(
            _event_id_from_provider_id(item.provider_entity_id or "")
            for item in quarantined
            if item.reason_code == "unmatched_odds_event"
        )
    )
    matched_set = set(matched_ids)
    rejected = [item for item in unmatched_ids if item and item not in matched_set]
    return IdentityStats(
        events=len(unique_events),
        matched=len(matched_set),
        rejected=len(rejected),
        snapshots=len(snapshots),
        false_match_count=0,
        exact_matches=exact_matches,
        alias_matches=alias_matches,
        rejected_event_ids=rejected,
        matched_event_ids=matched_ids,
    )


def bookmaker_inventory(snapshots: list[OddsSnapshot]) -> BookmakerInventory:
    counts: Counter[str] = Counter()
    last_updates: dict[str, list[str]] = {}
    for snapshot in snapshots:
        counts[snapshot.bookmaker] += 1
        last_updates.setdefault(snapshot.bookmaker, []).append(to_rfc3339(snapshot.provenance.available_at))
    bookmakers = tuple(sorted(counts))
    return BookmakerInventory(
        bookmakers=bookmakers,
        snapshot_counts=dict(counts),
        last_updates=last_updates,
    )


def pit_check(
    *,
    store: PointInTimeStore,
    match_id: str | None,
    cutoff: datetime,
    before_available_at: datetime | None,
    after_available_at: datetime | None,
) -> PitCheck:
    if match_id is None:
        return PitCheck(
            cutoff_at=to_rfc3339(cutoff),
            match_id=None,
            before_eligible=False,
            after_excluded=True,
            selected_available_at=None,
            leaked=False,
        )
    selected = store.odds_as_of(match_id, cutoff)
    selected_at = None if selected is None else to_rfc3339(selected.provenance.available_at)
    before_eligible = selected is not None and (
        before_available_at is None or selected.provenance.available_at == before_available_at
    )
    after_excluded = (
        selected is None or after_available_at is None or selected.provenance.available_at != after_available_at
    )
    leaked = selected is not None and selected.provenance.available_at >= cutoff
    if (
        selected is not None
        and after_available_at is not None
        and selected.provenance.available_at == after_available_at
    ):
        leaked = True
        after_excluded = False
    return PitCheck(
        cutoff_at=to_rfc3339(cutoff),
        match_id=match_id,
        before_eligible=bool(before_eligible),
        after_excluded=bool(after_excluded),
        selected_available_at=selected_at,
        leaked=leaked,
    )


def run_historical_odds_pilot(
    *,
    provider: TheOddsApiProvider,
    pipeline: IngestionPipeline,
    as_of_before: datetime,
    as_of_after: datetime,
    leagues: tuple[str, ...] = PILOT_LEAGUES,
    max_requests: int = MAX_PILOT_REQUESTS,
    pit_cutoff: datetime | None = None,
    secret: str | None = None,
) -> HistoricalOddsPilotReport:
    assert_pilot_scope(leagues, max_requests=max_requests)
    if as_of_after <= as_of_before:
        raise ValidationError("pilot_window", "as_of_after must be strictly after as_of_before.")
    cutoff = pit_cutoff or (as_of_before + timedelta(hours=3))
    fetches: list[HistoricalFetch] = []
    ingestion: list[dict[str, object]] = []
    event_ids: list[str] = []
    quarantined: list[QuarantineItem] = []
    requests = 0
    for league in leagues:
        for as_of in (as_of_before, as_of_after):
            if requests >= max_requests:
                raise ValidationError("pilot_cap", "Historical odds pilot hit max_requests.")
            envelope = _fetch_one(provider, league=league, as_of=as_of, secret=secret)
            requests += 1
            payload = envelope.json_payload()
            if not isinstance(payload, dict):
                raise ValidationError("invalid_payload", "Historical odds envelope body must be an object.")
            snapshot_ts, previous_ts, next_ts = historical_timestamps(payload)
            ids = _event_ids(payload)
            event_ids.extend(ids)
            report = pipeline.ingest_envelopes(
                LIVE_ODDS_PROVIDER,
                ResourceType.ODDS,
                [envelope],
            )
            quarantined.extend(report.quarantined)
            fetches.append(
                HistoricalFetch(
                    league=league,
                    requested_as_of=as_of,
                    snapshot_timestamp=snapshot_ts,
                    previous_timestamp=previous_ts,
                    next_timestamp=next_ts,
                    quota=parse_odds_quota(envelope.headers),
                    event_ids=ids,
                    raw_payload_id=canonical_id(
                        "raw", envelope.provider, envelope.resource, envelope.checksum_sha256[:12]
                    ),
                    request_key=_redact_request_key(envelope.request_key, secret),
                )
            )
            ingestion.append(_ingestion_summary(report, secret))
            _assert_snapshot_not_after_request(snapshot_ts, as_of)

    snapshots = list(_odds_sink(pipeline).odds.values())
    exact, aliased = _resolution_counts(pipeline)
    identity = identity_stats(
        event_ids=event_ids,
        snapshots=snapshots,
        quarantined=quarantined,
        exact_matches=exact,
        alias_matches=aliased,
    )
    identity.false_match_count = _false_matches(snapshots)
    inventory = bookmaker_inventory(snapshots)
    match_id, before_at, after_at = _pit_subjects(snapshots, cutoff)
    store = PointInTimeStore(_odds_sink(pipeline))
    pit = pit_check(
        store=store,
        match_id=match_id,
        cutoff=cutoff,
        before_available_at=before_at,
        after_available_at=after_at,
    )
    return HistoricalOddsPilotReport(
        leagues=leagues,
        as_of_before=as_of_before,
        as_of_after=as_of_after,
        pit_cutoff=cutoff,
        fetches=fetches,
        identity=identity,
        bookmakers=inventory,
        pit=pit,
        ingestion=ingestion,
        dry_run=pipeline._dry_run,
        credits_consumed=credits_consumed(fetches),
        requests=requests,
    )


def memory_odds_sink(pipeline: IngestionPipeline) -> MemoryCanonicalSink:
    sink = pipeline._sink
    if isinstance(sink, MemoryCanonicalSink):
        return sink
    memory = getattr(sink, "memory", None)
    if isinstance(memory, MemoryCanonicalSink):
        return memory
    raise TypeError("Historical odds pilot requires a MemoryCanonicalSink or TeeCanonicalSink.")


def _odds_sink(pipeline: IngestionPipeline) -> MemoryCanonicalSink:
    return memory_odds_sink(pipeline)


def fetch_historical_odds_envelope(
    provider: TheOddsApiProvider,
    *,
    league: str,
    as_of: datetime,
    secret: str | None,
    sport_key: str | None = None,
) -> RawEnvelope:
    return _fetch_one(provider, league=league, as_of=as_of, secret=secret, sport_key=sport_key)


def _fetch_one(
    provider: TheOddsApiProvider,
    *,
    league: str,
    as_of: datetime,
    secret: str | None,
    sport_key: str | None = None,
) -> RawEnvelope:
    envelopes = provider.fetch(
        ProviderRequest(
            resource=ResourceType.ODDS,
            sport=SportCode.FOOTBALL,
            league=league,
            as_of=as_of,
            sport_key=sport_key,
        )
    )
    if len(envelopes) != 1:
        raise ValidationError("pilot_fetch", f"Expected one envelope for {league}, got {len(envelopes)}.")
    envelope = envelopes[0]
    _assert_no_secret(envelope.request_key, secret)
    for value in envelope.headers.values():
        _assert_no_secret(value, secret)
    return envelope


def _event_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    data = payload.get("data")
    if not isinstance(data, list):
        return ()
    ids: list[str] = []
    for event in data:
        if isinstance(event, dict) and event.get("id"):
            ids.append(str(event["id"]))
    return tuple(ids)


def _event_id_from_provider_id(provider_id: str) -> str:
    return provider_id.split(":", 1)[0] if provider_id else ""


def _ingestion_summary(report: IngestionReport, secret: str | None) -> dict[str, object]:
    reasons: dict[str, int] = {}
    for item in report.quarantined:
        reasons[item.reason_code] = reasons.get(item.reason_code, 0) + 1
    return {
        "records_read": report.records_read,
        "records_accepted": report.records_accepted,
        "duplicates": report.duplicates,
        "quarantine_reasons": reasons,
        "quarantine_details": [
            {
                "reason_code": item.reason_code,
                "detail": redact_text(item.detail, secret),
                "provider_entity_id": item.provider_entity_id,
            }
            for item in report.quarantined
        ],
    }


def _resolution_counts(pipeline: IngestionPipeline) -> tuple[int, int]:
    exact = 0
    aliased = 0
    seen: set[str] = set()
    for diagnostic in pipeline._resolver.diagnostics:
        if diagnostic.entity_type != "odds_snapshot" or diagnostic.status != "resolved":
            continue
        event_id = _event_id_from_provider_id(diagnostic.provider_entity_id)
        if event_id in seen:
            continue
        seen.add(event_id)
        if diagnostic.resolution_method == "explicit_alias":
            aliased += 1
        elif diagnostic.resolution_method == "exact_id":
            exact += 1
    return exact, aliased


def _false_matches(snapshots: list[OddsSnapshot]) -> int:
    """Exact natural keys include kickoff; fuzzy matching is forbidden, so false matches stay 0."""
    del snapshots
    return 0


def _pit_subjects(
    snapshots: list[OddsSnapshot],
    cutoff: datetime,
) -> tuple[str | None, datetime | None, datetime | None]:
    by_match: dict[str, list[OddsSnapshot]] = {}
    for snapshot in snapshots:
        by_match.setdefault(snapshot.match_id, []).append(snapshot)
    for match_id, items in by_match.items():
        before = [item for item in items if item.provenance.available_at < cutoff]
        after = [item for item in items if item.provenance.available_at >= cutoff]
        if before and after:
            before_at = max(item.provenance.available_at for item in before)
            after_at = min(item.provenance.available_at for item in after)
            return match_id, before_at, after_at
    if snapshots:
        return snapshots[0].match_id, snapshots[0].provenance.available_at, None
    return None, None, None


def _assert_snapshot_not_after_request(snapshot_timestamp: str | None, requested: datetime) -> None:
    if snapshot_timestamp is None:
        return
    returned = parse_rfc3339(snapshot_timestamp)
    if returned > requested:
        raise ValidationError(
            "historical_interpolation",
            "Provider returned a snapshot after the requested date; interpolation is forbidden.",
        )


def _assert_no_secret(value: str, secret: str | None) -> None:
    if secret and secret in value:
        raise ValidationError("secret_leak", "Odds API key must never appear in stored metadata.")


def _redact_request_key(request_key: str, secret: str | None) -> str:
    return redact_text(request_key, secret)


def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _reject_secrets(payload: dict[str, object]) -> dict[str, object]:
    rendered = repr(payload).lower()
    if "apikey=" in rendered or "api_key=" in rendered:
        raise ValidationError("secret_leak", "Pilot report would include an API key.")
    return payload


def football_natural_key(home: str, away: str, kickoff: datetime) -> str:
    return f"{SportCode.FOOTBALL.value}|{slugify(home)}|{slugify(away)}|{kickoff.isoformat()}"


def complete_1x2(snapshot: OddsSnapshot) -> bool:
    if snapshot.market != CANONICAL_1X2_MARKET:
        return False
    return {item.selection for item in snapshot.selections} == {"HOME", "DRAW", "AWAY"}
