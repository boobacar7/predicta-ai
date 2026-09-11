from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicta_ingestion.canonical.models import CanonicalBatch, OddsSnapshot
from predicta_ingestion.clock import parse_rfc3339, to_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.historical_odds import (
    CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED,
    PILOT_LEAGUES,
    VALUE_SNAPSHOT_RULE,
    BookmakerInventory,
    HistoricalFetch,
    IdentityStats,
    PitCheck,
    bookmaker_inventory,
    complete_1x2,
    credits_consumed,
    fetch_historical_odds_envelope,
    identity_stats,
    memory_odds_sink,
    parse_odds_quota,
    pit_check,
)
from predicta_ingestion.ids import canonical_id
from predicta_ingestion.persistence.memory import CanonicalSink, MemoryCanonicalSink, PersistResult
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.pit.store import PointInTimeStore
from predicta_ingestion.providers.leagues import normalize_league_slug, resolve_v1_leagues
from predicta_ingestion.providers.the_odds_api import TheOddsApiProvider
from predicta_ingestion.quality.quarantine import QuarantineItem
from predicta_ingestion.raw.store import StoredRaw
from predicta_ingestion.secrets import redact_text

PERSIST_WINDOW_START = datetime.fromisoformat("2026-08-21T00:00:00+00:00")
PERSIST_WINDOW_END = datetime.fromisoformat("2026-08-25T00:00:00+00:00")
MAX_PERSIST_REQUESTS = 8
MIN_SLOT_GAP = timedelta(hours=12)
EXPECTED_WINDOW_MATCH_COUNT = 19
EXPECTED_TARGET_MATCH_COUNT = 17
ISOLATED_PARIS_MATCH_ID = "mth_football-sportmonks-19715629"
INVERTED_PSG_RENNES_MATCH_ID = "mth_football-sportmonks-19715631"
KNOWN_IDENTITY_EXCLUSIONS: dict[str, str] = {
    ISOLATED_PARIS_MATCH_ID: "isolated_team: Paris / Paris FC / PSG kept distinct",
    INVERTED_PSG_RENNES_MATCH_ID: "inverted_home_away: PSG/Rennes vs Rennes/PSG",
}
PERSIST_LEAGUE_NAMES = frozenset({"Premier League", "Ligue 1"})
PERSIST_CADENCE = (
    "One historical request per league per kickoff day. "
    "as_of equals the earliest kickoff that day so the provider returns the "
    "closest snapshot <= kickoff. Sub-daily / 5-minute walking is refused."
)


@dataclass(frozen=True)
class PilotMatch:
    match_id: str
    home_team: str
    away_team: str
    home_team_id: str
    away_team_id: str
    league: str
    league_slug: str
    kickoff_at: datetime

    def to_dict(self) -> dict[str, str]:
        return {
            "match_id": self.match_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "league": self.league,
            "league_slug": self.league_slug,
            "kickoff_at": to_rfc3339(self.kickoff_at),
            "identity_exclusion": KNOWN_IDENTITY_EXCLUSIONS.get(self.match_id, ""),
        }


@dataclass(frozen=True)
class PersistSlot:
    league: str
    as_of: datetime
    kickoff_date: str

    def to_dict(self) -> dict[str, str]:
        return {
            "league": self.league,
            "as_of": to_rfc3339(self.as_of),
            "kickoff_date": self.kickoff_date,
        }


@dataclass(frozen=True)
class ObservedEvent:
    event_id: str
    home_team: str
    away_team: str
    commence_at: datetime
    league: str
    in_window: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "commence_at": to_rfc3339(self.commence_at),
            "league": self.league,
            "in_window": self.in_window,
        }


@dataclass
class PersistHistoricalOddsReport:
    leagues: tuple[str, ...]
    window_start: datetime
    window_end: datetime
    slots: tuple[PersistSlot, ...]
    fetches: list[HistoricalFetch]
    identity: IdentityStats
    bookmakers: BookmakerInventory
    pit: PitCheck
    ingestion: list[dict[str, object]]
    matches: tuple[PilotMatch, ...]
    observed_events: list[ObservedEvent]
    skipped_out_of_scope: list[str]
    dry_run: bool
    credits_consumed: int | None
    requests: int
    stop_reason: str | None
    raw_payload_ids: list[str]
    documented_credits_per_request: int = CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    cadence: str = PERSIST_CADENCE
    value_snapshot_rule: str = VALUE_SNAPSHOT_RULE

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "leagues": list(self.leagues),
            "window_start": to_rfc3339(self.window_start),
            "window_end": to_rfc3339(self.window_end),
            "cadence": self.cadence,
            "value_snapshot_rule": self.value_snapshot_rule,
            "requests": self.requests,
            "credits_consumed": self.credits_consumed,
            "documented_credits_per_request": self.documented_credits_per_request,
            "dry_run": self.dry_run,
            "stop_reason": self.stop_reason,
            "slots": [item.to_dict() for item in self.slots],
            "fetches": [item.to_dict() for item in self.fetches],
            "identity": self.identity.to_dict(),
            "bookmakers": self.bookmakers.to_dict(),
            "pit": self.pit.to_dict(),
            "ingestion": self.ingestion,
            "matches": [item.to_dict() for item in self.matches],
            "observed_events": [item.to_dict() for item in self.observed_events],
            "skipped_out_of_scope_match_ids": list(dict.fromkeys(self.skipped_out_of_scope)),
            "raw_payload_ids": self.raw_payload_ids,
            "target_match_ids": [item.match_id for item in self.matches],
            "known_identity_exclusions": dict(KNOWN_IDENTITY_EXCLUSIONS),
            "expected_window_matches": EXPECTED_WINDOW_MATCH_COUNT,
            "expected_target_matches": EXPECTED_TARGET_MATCH_COUNT,
        }
        return _reject_secrets(payload)


class TargetMatchOddsSink:
    """Persist odds only for the bounded weekend match ids. Extra Sportmonks hits are skipped."""

    def __init__(self, inner: CanonicalSink, target_match_ids: frozenset[str]) -> None:
        self._inner = inner
        self._target_match_ids = target_match_ids
        self.skipped_match_ids: list[str] = []

    @property
    def memory(self) -> MemoryCanonicalSink:
        inner = self._inner
        if isinstance(inner, MemoryCanonicalSink):
            return inner
        memory = getattr(inner, "memory", None)
        if isinstance(memory, MemoryCanonicalSink):
            return memory
        raise TypeError("TargetMatchOddsSink requires an inner memory sink.")

    def persist(self, batch: CanonicalBatch) -> PersistResult:
        kept: list[OddsSnapshot] = []
        for snapshot in batch.odds:
            if snapshot.match_id in self._target_match_ids:
                kept.append(snapshot)
            else:
                self.skipped_match_ids.append(snapshot.match_id)
        return self._inner.persist(batch.model_copy(update={"odds": kept}))

    def record_raw(self, stored: StoredRaw) -> None:
        self._inner.record_raw(stored)

    def persist_identity(self, bindings: object) -> None:
        self._inner.persist_identity(bindings)

    def record_quarantine(self, **kwargs: object) -> None:
        recorder = getattr(self._inner, "record_quarantine", None)
        if callable(recorder):
            recorder(**kwargs)

    def record_run(self, **kwargs: object) -> None:
        recorder = getattr(self._inner, "record_run", None)
        if callable(recorder):
            recorder(**kwargs)


def plan_persist_slots(matches: tuple[PilotMatch, ...]) -> tuple[PersistSlot, ...]:
    by_league_day: dict[tuple[str, str], list[datetime]] = {}
    for match in matches:
        if match.league_slug not in PILOT_LEAGUES:
            raise ValidationError(
                "persist_scope",
                f"Persist runner only accepts premier-league and ligue-1, not {match.league_slug}.",
            )
        day = match.kickoff_at.date().isoformat()
        by_league_day.setdefault((match.league_slug, day), []).append(match.kickoff_at)
    slots = [
        PersistSlot(league=league, as_of=min(kickoffs), kickoff_date=day)
        for (league, day), kickoffs in sorted(by_league_day.items())
    ]
    return tuple(slots)


def assert_persist_scope(
    slots: tuple[PersistSlot, ...],
    *,
    max_requests: int,
    request_cap: int = MAX_PERSIST_REQUESTS,
) -> None:
    if max_requests > request_cap:
        raise ValidationError(
            "persist_cap",
            f"Historical odds persist runner refuses more than {request_cap} requests.",
        )
    leagues = {item.league for item in slots}
    unknown = sorted(leagues - set(PILOT_LEAGUES))
    if unknown:
        raise ValidationError(
            "persist_scope",
            "Historical odds persist runner only accepts premier-league and ligue-1, "
            f"not {', '.join(unknown)}.",
        )
    if len(slots) > max_requests:
        raise ValidationError(
            "persist_cap",
            f"Persist window needs {len(slots)} requests but max_requests={max_requests}.",
        )
    by_league: dict[str, list[datetime]] = {}
    for slot in slots:
        resolve_v1_leagues(slot.league)
        by_league.setdefault(slot.league, []).append(slot.as_of)
    for league, times in by_league.items():
        ordered = sorted(times)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current - previous < MIN_SLOT_GAP:
                raise ValidationError(
                    "persist_cadence",
                    f"Refusing sub-daily historical cadence for {league} "
                    f"({to_rfc3339(previous)} then {to_rfc3339(current)}). "
                    "This runner is not a 5-minute backfill.",
                )


def assert_strict_weekend_window(matches: tuple[PilotMatch, ...]) -> None:
    if len(matches) != EXPECTED_WINDOW_MATCH_COUNT:
        raise ValidationError(
            "persist_window",
            "Expected "
            f"{EXPECTED_WINDOW_MATCH_COUNT} PL+Ligue 1 matches in "
            f"{to_rfc3339(PERSIST_WINDOW_START)}–{to_rfc3339(PERSIST_WINDOW_END)}; "
            f"SQL returned {len(matches)}. Refusing to guess the universe.",
        )
    ids = {item.match_id for item in matches}
    missing = sorted(set(KNOWN_IDENTITY_EXCLUSIONS) - ids)
    if missing:
        raise ValidationError(
            "persist_window",
            "Known identity exclusions are missing from the SQL weekend window: "
            + ", ".join(missing),
        )
    for match in matches:
        if match.kickoff_at < PERSIST_WINDOW_START or match.kickoff_at >= PERSIST_WINDOW_END:
            raise ValidationError(
                "persist_window",
                f"Match {match.match_id} kickoff {to_rfc3339(match.kickoff_at)} is outside the persist window.",
            )
        if match.league not in PERSIST_LEAGUE_NAMES and match.league_slug not in PILOT_LEAGUES:
            raise ValidationError(
                "persist_scope",
                f"Match {match.match_id} league {match.league!r} is outside Premier League / Ligue 1.",
            )


def load_matches_from_sql(
    engine: Engine,
    *,
    window_start: datetime,
    window_end: datetime,
) -> tuple[PilotMatch, ...]:
    query = text(
        """
        SELECT m.id, m.kickoff_at, m.home_team_id, m.away_team_id,
               ht.name AS home_name, at.name AS away_name,
               l.name AS league_name, l.slug AS league_slug
        FROM matches m
        JOIN teams ht ON ht.id = m.home_team_id
        JOIN teams at ON at.id = m.away_team_id
        JOIN leagues l ON l.id = m.league_id
        WHERE m.kickoff_at >= :window_start
          AND m.kickoff_at < :window_end
          AND (
                l.slug IN ('premier-league', 'ligue-1')
                OR lower(l.name) IN ('premier league', 'ligue 1')
          )
        ORDER BY m.kickoff_at, m.id
        """
    )
    matches: list[PilotMatch] = []
    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"window_start": window_start, "window_end": window_end},
        ).mappings()
        for row in rows:
            kickoff = row["kickoff_at"]
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=window_start.tzinfo)
            league_name = str(row["league_name"])
            slug_raw = str(row["league_slug"] or "")
            slug = normalize_league_slug(slug_raw) if slug_raw else normalize_league_slug(league_name.lower())
            matches.append(
                PilotMatch(
                    match_id=str(row["id"]),
                    home_team=str(row["home_name"]),
                    away_team=str(row["away_name"]),
                    home_team_id=str(row["home_team_id"]),
                    away_team_id=str(row["away_team_id"]),
                    league=league_name,
                    league_slug=slug,
                    kickoff_at=kickoff,
                )
            )
    return tuple(matches)


def load_weekend_matches_from_sql(engine: Engine) -> tuple[PilotMatch, ...]:
    return load_matches_from_sql(
        engine,
        window_start=PERSIST_WINDOW_START,
        window_end=PERSIST_WINDOW_END,
    )


def run_persist_historical_odds_pilot(
    *,
    provider: TheOddsApiProvider,
    pipeline: IngestionPipeline,
    matches: tuple[PilotMatch, ...],
    slots: tuple[PersistSlot, ...] | None = None,
    max_requests: int = MAX_PERSIST_REQUESTS,
    strict_window: bool = True,
    secret: str | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    request_cap: int = MAX_PERSIST_REQUESTS,
) -> PersistHistoricalOddsReport:
    start = window_start or PERSIST_WINDOW_START
    end = window_end or PERSIST_WINDOW_END
    if strict_window:
        assert_strict_weekend_window(matches)
    planned = slots or plan_persist_slots(matches)
    assert_persist_scope(planned, max_requests=max_requests, request_cap=request_cap)
    fetches: list[HistoricalFetch] = []
    ingestion: list[dict[str, object]] = []
    quarantined: list[QuarantineItem] = []
    observed_events: list[ObservedEvent] = []
    raw_payload_ids: list[str] = []
    requests = 0
    stop_reason: str | None = None
    remaining_credits: int | None = None
    for slot in planned:
        remaining_slots = len(planned) - requests
        if remaining_credits is not None and remaining_credits < CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED:
            stop_reason = (
                "Remaining The Odds API credits are below one historical request; "
                "the persist runner stopped instead of expanding or guessing."
            )
            break
        needed = remaining_slots * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
        if remaining_credits is not None and remaining_credits < needed:
            stop_reason = (
                "Remaining credits cannot cover the remaining bounded slots; "
                "the persist runner stopped instead of silently shrinking the window."
            )
            break
        if requests >= max_requests:
            stop_reason = "max_requests reached."
            break
        envelope = fetch_historical_odds_envelope(
            provider,
            league=slot.league,
            as_of=slot.as_of,
            secret=secret,
        )
        requests += 1
        payload = envelope.json_payload()
        if not isinstance(payload, dict):
            raise ValidationError("invalid_payload", "Historical odds envelope body must be an object.")
        quota = parse_odds_quota(envelope.headers)
        if quota.requests_last is not None and quota.requests_last > CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED:
            stop_reason = (
                f"Provider charged {quota.requests_last} credits for one historical request "
                f"(documented {CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED}). Remaining fetches aborted."
            )
            fetches.append(_fetch_record(envelope, slot=slot, payload=payload, secret=secret))
            raw_payload_ids.append(fetches[-1].raw_payload_id or "")
            break
        remaining_credits = quota.requests_remaining
        snapshot_ts, _previous_ts, _next_ts = (
            payload.get("snapshot_timestamp"),
            payload.get("previous_timestamp"),
            payload.get("next_timestamp"),
        )
        if isinstance(snapshot_ts, str) and snapshot_ts:
            returned = parse_rfc3339(snapshot_ts)
            if returned > slot.as_of:
                raise ValidationError(
                    "historical_interpolation",
                    "Provider returned a snapshot after the requested date; interpolation is forbidden.",
                )
        observed = _observed_events(
            payload,
            league=slot.league,
            window_start=start,
            window_end=end,
        )
        observed_events.extend(observed)
        report = pipeline.ingest_envelopes(
            envelope.provider,
            envelope.resource,
            [envelope],
        )
        quarantined.extend(report.quarantined)
        fetch = _fetch_record(envelope, slot=slot, payload=payload, secret=secret)
        fetches.append(fetch)
        if fetch.raw_payload_id:
            raw_payload_ids.append(fetch.raw_payload_id)
        ingestion.append(_ingestion_summary(report, secret))

    snapshots = list(memory_odds_sink(pipeline).odds.values())
    unique_observed = _unique_events(observed_events)
    window_event_ids = [item.event_id for item in unique_observed if item.in_window]
    window_event_set = set(window_event_ids)
    exact, aliased = _resolution_counts(pipeline, window_event_ids=window_event_set)
    window_quarantined = [
        item
        for item in quarantined
        if item.reason_code != "unmatched_odds_event"
        or (item.provider_entity_id or "").split(":", 1)[0] in window_event_set
    ]
    identity = identity_stats(
        event_ids=window_event_ids,
        snapshots=snapshots,
        quarantined=window_quarantined,
        exact_matches=exact,
        alias_matches=aliased,
    )
    identity.false_match_count = 0
    inventory = bookmaker_inventory(snapshots)
    pit = _weekend_pit_check(pipeline, matches, snapshots)
    skipped: list[str] = []
    sink = pipeline._sink
    if isinstance(sink, TargetMatchOddsSink):
        skipped = list(sink.skipped_match_ids)
    return PersistHistoricalOddsReport(
        leagues=PILOT_LEAGUES,
        window_start=start,
        window_end=end,
        slots=planned,
        fetches=fetches,
        identity=identity,
        bookmakers=inventory,
        pit=pit,
        ingestion=ingestion,
        matches=matches,
        observed_events=unique_observed,
        skipped_out_of_scope=skipped,
        dry_run=pipeline._dry_run,
        credits_consumed=credits_consumed(fetches),
        requests=requests,
        stop_reason=stop_reason,
        raw_payload_ids=[item for item in raw_payload_ids if item],
    )


def target_match_ids(matches: tuple[PilotMatch, ...]) -> frozenset[str]:
    return frozenset(item.match_id for item in matches)


def _weekend_pit_check(
    pipeline: IngestionPipeline,
    matches: tuple[PilotMatch, ...],
    snapshots: list[OddsSnapshot],
) -> PitCheck:
    by_match: dict[str, list[OddsSnapshot]] = {}
    for snapshot in snapshots:
        by_match.setdefault(snapshot.match_id, []).append(snapshot)
    store = PointInTimeStore(memory_odds_sink(pipeline))
    for match in matches:
        if match.match_id in KNOWN_IDENTITY_EXCLUSIONS:
            continue
        items = by_match.get(match.match_id, [])
        if not items:
            continue
        after = [item for item in items if item.provenance.available_at > match.kickoff_at]
        before = [item for item in items if item.provenance.available_at <= match.kickoff_at]
        before_at = max((item.provenance.available_at for item in before), default=None)
        after_at = min((item.provenance.available_at for item in after), default=None)
        return pit_check(
            store=store,
            match_id=match.match_id,
            cutoff=match.kickoff_at,
            before_available_at=before_at,
            after_available_at=after_at,
        )
    if matches:
        return pit_check(
            store=store,
            match_id=matches[0].match_id,
            cutoff=matches[0].kickoff_at,
            before_available_at=None,
            after_available_at=None,
        )
    return pit_check(
        store=store,
        match_id=None,
        cutoff=PERSIST_WINDOW_START,
        before_available_at=None,
        after_available_at=None,
    )


def _fetch_record(
    envelope: Any,
    *,
    slot: PersistSlot,
    payload: dict[str, Any],
    secret: str | None,
) -> HistoricalFetch:
    from predicta_ingestion.historical_odds import historical_timestamps

    snapshot_ts, previous_ts, next_ts = historical_timestamps(payload)
    ids = tuple(
        str(event["id"])
        for event in payload.get("data", [])
        if isinstance(event, dict) and event.get("id")
    )
    return HistoricalFetch(
        league=slot.league,
        requested_as_of=slot.as_of,
        snapshot_timestamp=snapshot_ts,
        previous_timestamp=previous_ts,
        next_timestamp=next_ts,
        quota=parse_odds_quota(envelope.headers),
        event_ids=ids,
        raw_payload_id=canonical_id(
            "raw", envelope.provider, envelope.resource, envelope.checksum_sha256[:12]
        ),
        request_key=redact_text(envelope.request_key, secret),
    )


def _observed_events(
    payload: dict[str, Any],
    *,
    league: str,
    window_start: datetime = PERSIST_WINDOW_START,
    window_end: datetime = PERSIST_WINDOW_END,
) -> list[ObservedEvent]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    events: list[ObservedEvent] = []
    for event in data:
        if not isinstance(event, dict) or not event.get("id") or not event.get("commence_time"):
            continue
        commence = parse_rfc3339(str(event["commence_time"]))
        events.append(
            ObservedEvent(
                event_id=str(event["id"]),
                home_team=str(event.get("home_team") or ""),
                away_team=str(event.get("away_team") or ""),
                commence_at=commence,
                league=league,
                in_window=window_start <= commence < window_end,
            )
        )
    return events


def _unique_events(events: list[ObservedEvent]) -> list[ObservedEvent]:
    seen: dict[str, ObservedEvent] = {}
    for item in events:
        seen[item.event_id] = item
    return list(seen.values())


def _ingestion_summary(report: Any, secret: str | None) -> dict[str, object]:
    reasons: Counter[str] = Counter()
    details: list[dict[str, object]] = []
    for item in report.quarantined:
        reasons[item.reason_code] += 1
        details.append(
            {
                "reason_code": item.reason_code,
                "detail": redact_text(item.detail, secret),
                "provider_entity_id": item.provider_entity_id,
            }
        )
    return {
        "records_read": report.records_read,
        "records_accepted": report.records_accepted,
        "duplicates": report.duplicates,
        "quarantine_reasons": dict(reasons),
        "quarantine_details": details,
    }


def _resolution_counts(
    pipeline: IngestionPipeline,
    *,
    window_event_ids: set[str] | None = None,
) -> tuple[int, int]:
    exact = 0
    aliased = 0
    seen: set[str] = set()
    allowed = window_event_ids
    for diagnostic in pipeline._resolver.diagnostics:
        if diagnostic.entity_type != "odds_snapshot" or diagnostic.status != "resolved":
            continue
        event_id = (diagnostic.provider_entity_id or "").split(":", 1)[0]
        if allowed is not None and event_id not in allowed:
            continue
        if event_id in seen:
            continue
        seen.add(event_id)
        if diagnostic.resolution_method == "explicit_alias":
            aliased += 1
        elif diagnostic.resolution_method == "exact_id":
            exact += 1
    return exact, aliased


def _reject_secrets(payload: dict[str, object]) -> dict[str, object]:
    rendered = repr(payload).lower()
    if "apikey=" in rendered or "api_key=" in rendered:
        raise ValidationError("secret_leak", "Pilot report would include an API key.")
    return payload


def complete_target_snapshots(snapshots: list[OddsSnapshot]) -> list[OddsSnapshot]:
    return [item for item in snapshots if complete_1x2(item)]
