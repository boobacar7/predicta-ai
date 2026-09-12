from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicta_ingestion.canonical.enums import ResourceType
from predicta_ingestion.clock import parse_rfc3339, to_rfc3339
from predicta_ingestion.config import PACKAGE_ROOT
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.historical_odds import (
    CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED,
    VALUE_SNAPSHOT_RULE,
    parse_odds_quota,
)
from predicta_ingestion.identity.historical import franchise_key, mls_slugs_for_name
from predicta_ingestion.oos_historical_odds import (
    DEFAULT_PARQUET_PATH,
    EXPECTED_OOS_MATCH_COUNT,
    OOS_END,
    OOS_LEAGUES,
    OOS_START,
    build_coverage_matrix,
    coalesce_slots,
    existing_historical_request_keys,
    historical_request_key,
    isolated_oos_match_ids,
    load_oos_matches,
    match_odds_states,
    partition_oos_slots,
    table_counts,
)
from predicta_ingestion.persist_historical_odds import (
    PersistHistoricalOddsReport,
    PersistSlot,
    PilotMatch,
    assert_persist_scope,
    plan_persist_slots,
    run_persist_historical_odds_pilot,
)
from predicta_ingestion.pipeline import IngestionPipeline, IngestionReport
from predicta_ingestion.providers.the_odds_api import (
    DEFAULT_MARKETS,
    DEFAULT_REGIONS,
    LIVE_ODDS_PROVIDER,
    LIVE_ODDS_SOURCE,
    TheOddsApiProvider,
)
from predicta_ingestion.raw.envelope import RawEnvelope
from predicta_ingestion.raw.store import StoredRaw

CHAMPIONS_LEAGUE_SLUG = "champions-league"
CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY = "soccer_uefa_champs_league_qualification"
MLS_SPORT_KEY = "soccer_usa_mls"
CHAMPS_LEAGUE_SPORT_KEY = "soccer_uefa_champs_league"
KICKOFF_ALIGN_SECONDS = 120
MAX_FINAL_BATCH_CREDITS = 10_000
PREFERRED_FINAL_BATCH_CREDITS = 8_000
MAX_FINAL_BATCH_REQUESTS = MAX_FINAL_BATCH_CREDITS // CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
FINAL_BATCH_KIND = "expand_oos_final_odds_batch"
REPO_ROOT = PACKAGE_ROOT.parent.parent
DEFAULT_REPORT_PATH = REPO_ROOT / "workers" / "ml" / "reports" / "oos-odds-final-batch.json"
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "qa" / "oos-odds-final-batch.md"


@dataclass(frozen=True)
class HistoricalEvent:
    sport_key: str
    home_team: str
    away_team: str
    commence_at: datetime
    event_id: str
    request_key: str


@dataclass
class FinalBatchEstimate:
    matches: tuple[PilotMatch, ...]
    covered_match_ids: frozenset[str]
    isolated_match_ids: frozenset[str]
    existing_request_keys: frozenset[str]
    planned_league_days: tuple[PersistSlot, ...]
    skipped_already_requested: tuple[PersistSlot, ...]
    skipped_already_persisted: tuple[PersistSlot, ...]
    skipped_identity_only: tuple[PersistSlot, ...]
    skipped_wrong_sport_key: tuple[PersistSlot, ...]
    coalesced_slots: tuple[PersistSlot, ...]
    replay_sport_keys: tuple[str, ...]
    replay_payload_count: int
    expected_replay_match_ids: frozenset[str]
    fetch_slots: tuple[PersistSlot, ...]
    fetch_match_ids: frozenset[str]
    expected_fetch_match_ids: frozenset[str]
    documented_credits_per_request: int = CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    estimated_credits: int = 0
    max_credits: int = MAX_FINAL_BATCH_CREDITS
    stop_reason: str | None = None
    plan_sha256: str = ""
    qualification_unavailable: bool = False

    @property
    def uncovered_count(self) -> int:
        return len(self.matches) - len(self.covered_match_ids)

    def expected_additional_coverage(self) -> int:
        return len(self.expected_replay_match_ids | self.expected_fetch_match_ids)

    def expected_final_coverage(self) -> int:
        return min(len(self.matches), len(self.covered_match_ids) + self.expected_additional_coverage())

    def plan_summary(self) -> dict[str, object]:
        return {
            "kind": FINAL_BATCH_KIND,
            "total_target_matches": EXPECTED_OOS_MATCH_COUNT,
            "already_covered": len(self.covered_match_ids),
            "uncovered": self.uncovered_count,
            "planned_requests": len(self.fetch_slots),
            "estimated_credits": self.estimated_credits,
            "expected_additional_coverage": self.expected_additional_coverage(),
            "expected_final_coverage": f"{self.expected_final_coverage()} / {EXPECTED_OOS_MATCH_COUNT}",
            "replay_payloads": self.replay_payload_count,
            "expected_replay_matches": len(self.expected_replay_match_ids),
            "expected_fetch_matches": len(self.expected_fetch_match_ids),
            "skipped_already_requested": len(self.skipped_already_requested),
            "skipped_already_persisted": len(self.skipped_already_persisted),
            "skipped_identity_only": len(self.skipped_identity_only),
            "skipped_wrong_sport_key": len(self.skipped_wrong_sport_key),
            "coalesced_slots": len(self.coalesced_slots),
            "max_credits": self.max_credits,
            "preferred_credits": PREFERRED_FINAL_BATCH_CREDITS,
            "stop_reason": self.stop_reason,
            "qualification_unavailable": self.qualification_unavailable,
            "fetch_slots": [item.to_dict() for item in self.fetch_slots],
            "plan_sha256": self.plan_sha256,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.plan_summary()
        payload.update(
            {
                "oos_start": to_rfc3339(OOS_START),
                "oos_end": to_rfc3339(OOS_END),
                "competitions": list(OOS_LEAGUES),
                "market": DEFAULT_MARKETS,
                "canonical_market": "1X2",
                "region": DEFAULT_REGIONS,
                "provider": LIVE_ODDS_PROVIDER,
                "source": LIVE_ODDS_SOURCE,
                "cadence": (
                    "One historical request per league per kickoff day. "
                    "Champions League qualifying uses soccer_uefa_champs_league_qualification. "
                    "Existing MLS franchise aliases are replayed from persisted raw payloads."
                ),
                "value_snapshot_rule": VALUE_SNAPSHOT_RULE,
                "isolated_matches": len(self.isolated_match_ids),
                "replay_sport_keys": list(self.replay_sport_keys),
                "existing_request_keys": len(self.existing_request_keys),
                "planned_league_days": len(self.planned_league_days),
                "qualification_sport_key": CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY,
            }
        )
        return payload


@dataclass
class FinalBatchReport:
    estimate: FinalBatchEstimate
    persist: PersistHistoricalOddsReport | None
    replay: dict[str, object]
    coverage_before: dict[str, object]
    coverage_after: dict[str, object]
    dry_run: bool
    estimate_only: bool
    credits_planned: int
    credits_consumed: int | None
    credits_remaining_before: int | None = None
    credits_remaining_after: int | None = None
    counts_before: dict[str, int] = field(default_factory=dict)
    counts_after: dict[str, int] = field(default_factory=dict)
    raw_payload_ids: list[str] = field(default_factory=list)
    sports_catalog_keys: list[str] = field(default_factory=list)
    requests_executed: int = 0
    requests_skipped: int = 0
    replay_duplicates: int = 0
    isolation: dict[str, int] = field(default_factory=dict)
    pit: dict[str, object] = field(default_factory=dict)
    identity: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        persist_payload: dict[str, object] | None = None
        if self.persist is not None:
            persist_payload = self.persist.to_dict()
        payload: dict[str, object] = {
            "kind": FINAL_BATCH_KIND,
            "plan": self.estimate.plan_summary(),
            "estimate": self.estimate.to_dict(),
            "estimate_only": self.estimate_only,
            "dry_run": self.dry_run,
            "credits_planned": self.credits_planned,
            "credits_consumed": self.credits_consumed,
            "credits_remaining_before": self.credits_remaining_before,
            "credits_remaining_after": self.credits_remaining_after,
            "requests_planned": len(self.estimate.fetch_slots),
            "requests_executed": self.requests_executed,
            "requests_skipped": self.requests_skipped,
            "requests_reused": len(self.estimate.skipped_already_requested),
            "replay": self.replay,
            "replay_duplicates": self.replay_duplicates,
            "counts_before": dict(self.counts_before),
            "counts_after": dict(self.counts_after),
            "coverage_before": self.coverage_before,
            "coverage_after": self.coverage_after,
            "persist": persist_payload,
            "raw_payload_ids": self.raw_payload_ids,
            "sports_catalog_keys": self.sports_catalog_keys,
            "isolation": dict(self.isolation),
            "pit": dict(self.pit),
            "identity": dict(self.identity),
            "cadence": VALUE_SNAPSHOT_RULE,
            "max_final_batch_credits": MAX_FINAL_BATCH_CREDITS,
        }
        return _reject_secrets(payload)


def existing_historical_request_keys_from_sql(engine: Engine) -> frozenset[str]:
    query = text(
        """
        SELECT DISTINCT provider_request_key
        FROM raw_payloads
        WHERE provider = 'the_odds_api'
          AND provider_request_key LIKE '%historical_odds%'
        """
    )
    with engine.connect() as connection:
        return frozenset(str(row[0]) for row in connection.execute(query) if row[0])


def load_historical_events(raw_root: Path) -> tuple[HistoricalEvent, ...]:
    events: list[HistoricalEvent] = []
    if not raw_root.is_dir():
        return ()
    for path in raw_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        request_key = payload.get("request_key")
        if not isinstance(request_key, str) or ":historical_odds:" not in request_key:
            continue
        body = payload.get("body_utf8")
        if not isinstance(body, str):
            continue
        try:
            inner = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(inner, dict):
            continue
        sport_key = str(inner.get("sport_key") or "")
        data = inner.get("data")
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict) or not item.get("commence_time"):
                continue
            try:
                commence = parse_rfc3339(str(item["commence_time"]))
            except (TypeError, ValueError):
                continue
            events.append(
                HistoricalEvent(
                    sport_key=sport_key,
                    home_team=str(item.get("home_team") or ""),
                    away_team=str(item.get("away_team") or ""),
                    commence_at=commence,
                    event_id=str(item.get("id") or ""),
                    request_key=request_key,
                )
            )
    return tuple(events)


def load_historical_stored_raw(raw_root: Path, *, sport_keys: frozenset[str]) -> list[StoredRaw]:
    items: list[StoredRaw] = []
    if not raw_root.is_dir():
        return items
    for path in raw_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        request_key = payload.get("request_key")
        if not isinstance(request_key, str) or ":historical_odds:" not in request_key:
            continue
        body = payload.get("body_utf8")
        if not isinstance(body, str):
            continue
        try:
            inner = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(inner, dict) or str(inner.get("sport_key") or "") not in sport_keys:
            continue
        resource = payload.get("resource") or "odds"
        envelope = RawEnvelope(
            provider=str(payload.get("provider") or LIVE_ODDS_PROVIDER),
            resource=resource,
            request_key=request_key,
            collected_at=payload.get("collected_at") or datetime.now(UTC),
            data_mode=payload.get("data_mode") or "live",
            body=body.encode("utf-8"),
            content_type=str(payload.get("content_type") or "application/json"),
            sport=payload.get("sport") or "football",
        )
        items.append(
            StoredRaw(
                raw_id=str(payload.get("id") or path.stem),
                envelope=envelope,
                storage_uri=str(path),
                duplicate=True,
            )
        )
    return items


def estimate_final_oos_odds_batch(
    *,
    engine: Engine | None = None,
    matches: tuple[PilotMatch, ...] | None = None,
    covered_ids: frozenset[str] | None = None,
    existing_request_keys: frozenset[str] | None = None,
    parquet_path: Path | None = None,
    raw_root: Path | None = None,
    events: tuple[HistoricalEvent, ...] | None = None,
    replay_payload_count: int | None = None,
    include_qualification: bool = True,
) -> FinalBatchEstimate:
    if matches is None:
        if engine is None:
            raise ValidationError(
                "oos_window",
                "Final OOS odds batch requires PostgreSQL or an explicit match universe.",
            )
        all_matches = load_oos_matches(engine, parquet_path=parquet_path)
    else:
        all_matches = matches
        _assert_oos_universe(all_matches)
    if covered_ids is None:
        if engine is None:
            known_ids: frozenset[str] = frozenset()
        else:
            known_ids = frozenset(
                item
                for item, state in match_odds_states(engine, all_matches).items()
                if state.has_valid_pre_match
            )
    else:
        known_ids = covered_ids
    isolated = isolated_oos_match_ids(all_matches)
    keys = existing_request_keys
    if keys is None:
        keys = existing_historical_request_keys(raw_root or Path())
        if engine is not None:
            keys = keys | existing_historical_request_keys_from_sql(engine)
    historical_events = events if events is not None else load_historical_events(raw_root or Path())
    planned = plan_persist_slots(all_matches, allowed_leagues=OOS_LEAGUES)
    fetch_slots, skipped_persisted, skipped_requested, skipped_identity = partition_oos_slots(
        planned,
        all_matches,
        covered_ids=known_ids,
        isolated_ids=isolated,
        existing_keys=keys,
    )
    fetch_slots, coalesced = coalesce_slots(fetch_slots)
    champs_league_fetch = tuple(item for item in fetch_slots if item.league == CHAMPIONS_LEAGUE_SLUG)
    remaining_fetch = tuple(item for item in fetch_slots if item.league != CHAMPIONS_LEAGUE_SLUG)
    qualification_slots: tuple[PersistSlot, ...] = ()
    if include_qualification:
        qualification_slots = plan_champions_league_qualification_slots(
            all_matches,
            covered_ids=known_ids,
            isolated_ids=isolated,
            existing_keys=keys,
            events=historical_events,
        )
        qualification_slots, qual_coalesced = coalesce_slots(qualification_slots)
    else:
        qual_coalesced = ()
    combined = remaining_fetch + qualification_slots
    combined, extra_coalesced = coalesce_slots(combined)
    replay_ids = expected_mls_replay_matches(all_matches, known_ids, isolated, historical_events)
    fetch_ids = expected_fetch_matches(all_matches, known_ids, isolated, combined, historical_events)
    stop_reason: str | None = None
    estimated = len(combined) * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    if estimated > MAX_FINAL_BATCH_CREDITS or len(combined) > MAX_FINAL_BATCH_REQUESTS:
        stop_reason = (
            f"Final OOS odds batch needs {len(combined)} requests / {estimated} credits "
            f"which exceeds MAX_FINAL_BATCH_CREDITS={MAX_FINAL_BATCH_CREDITS}. "
            "Refusing to execute."
        )
    replay_count = replay_payload_count
    if replay_count is None and raw_root is not None:
        replay_count = len(load_historical_stored_raw(raw_root, sport_keys=frozenset({MLS_SPORT_KEY})))
    return FinalBatchEstimate(
        matches=all_matches,
        covered_match_ids=known_ids,
        isolated_match_ids=isolated,
        existing_request_keys=keys,
        planned_league_days=planned,
        skipped_already_requested=skipped_requested,
        skipped_already_persisted=skipped_persisted,
        skipped_identity_only=skipped_identity,
        skipped_wrong_sport_key=champs_league_fetch,
        coalesced_slots=coalesced + qual_coalesced + extra_coalesced,
        replay_sport_keys=(MLS_SPORT_KEY,),
        replay_payload_count=replay_count or 0,
        expected_replay_match_ids=replay_ids,
        fetch_slots=combined,
        fetch_match_ids=frozenset(
            item.match_id
            for item in all_matches
            if item.match_id not in known_ids and item.match_id not in isolated
        ),
        expected_fetch_match_ids=fetch_ids,
        estimated_credits=estimated,
        stop_reason=stop_reason,
        plan_sha256=_slots_hash(combined),
        qualification_unavailable=not include_qualification,
    )


def plan_champions_league_qualification_slots(
    matches: tuple[PilotMatch, ...],
    *,
    covered_ids: frozenset[str],
    isolated_ids: frozenset[str],
    existing_keys: frozenset[str],
    events: tuple[HistoricalEvent, ...],
) -> tuple[PersistSlot, ...]:
    champs_commences = [item.commence_at for item in events if item.sport_key == CHAMPS_LEAGUE_SPORT_KEY]
    by_day: dict[str, list[PilotMatch]] = defaultdict(list)
    for match in matches:
        if match.league_slug != CHAMPIONS_LEAGUE_SLUG:
            continue
        if match.match_id in covered_ids or match.match_id in isolated_ids:
            continue
        if _kickoff_present(match.kickoff_at, champs_commences):
            continue
        by_day[match.kickoff_at.date().isoformat()].append(match)
    slots: list[PersistSlot] = []
    for day, day_matches in sorted(by_day.items()):
        as_of = min(item.kickoff_at for item in day_matches)
        slot = PersistSlot(
            league=CHAMPIONS_LEAGUE_SLUG,
            as_of=as_of,
            kickoff_date=day,
            sport_key=CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY,
        )
        key = historical_request_key(slot.league, slot.as_of, sport_key=slot.sport_key)
        if key in existing_keys:
            continue
        slots.append(slot)
    return tuple(slots)


def expected_mls_replay_matches(
    matches: tuple[PilotMatch, ...],
    covered_ids: frozenset[str],
    isolated_ids: frozenset[str],
    events: tuple[HistoricalEvent, ...],
) -> frozenset[str]:
    mls_events = [item for item in events if item.sport_key == MLS_SPORT_KEY]
    recovered: set[str] = set()
    for match in matches:
        if match.league_slug != "mls":
            continue
        if match.match_id in covered_ids or match.match_id in isolated_ids:
            continue
        if _mls_franchise_event(match, mls_events) is not None:
            recovered.add(match.match_id)
    return frozenset(recovered)


def expected_fetch_matches(
    matches: tuple[PilotMatch, ...],
    covered_ids: frozenset[str],
    isolated_ids: frozenset[str],
    slots: tuple[PersistSlot, ...],
    events: tuple[HistoricalEvent, ...],
) -> frozenset[str]:
    slot_days = {(item.league, item.kickoff_date) for item in slots}
    champs_commences = [item.commence_at for item in events if item.sport_key == CHAMPS_LEAGUE_SPORT_KEY]
    mls_events = [item for item in events if item.sport_key == MLS_SPORT_KEY]
    recovered: set[str] = set()
    for match in matches:
        if match.match_id in covered_ids or match.match_id in isolated_ids:
            continue
        day = match.kickoff_at.date().isoformat()
        if (match.league_slug, day) not in slot_days:
            continue
        if match.league_slug == CHAMPIONS_LEAGUE_SLUG:
            if not _kickoff_present(match.kickoff_at, champs_commences):
                recovered.add(match.match_id)
            continue
        if match.league_slug == "mls":
            if _mls_franchise_event(match, mls_events) is not None:
                continue
            if not _kickoff_present(match.kickoff_at, [item.commence_at for item in mls_events]):
                recovered.add(match.match_id)
    return frozenset(recovered)


def run_final_oos_odds_batch(
    *,
    provider: TheOddsApiProvider,
    pipeline: IngestionPipeline,
    estimate: FinalBatchEstimate,
    secret: str | None = None,
    estimate_only: bool = False,
    probe_quota: bool = False,
    engine: Engine | None = None,
    raw_root: Path | None = None,
    parquet_path: Path | None = None,
    coverage_before: dict[str, object] | None = None,
    counts_before: dict[str, int] | None = None,
) -> FinalBatchReport:
    if estimate.stop_reason:
        raise ValidationError("persist_cap", estimate.stop_reason)
    assert_persist_scope(
        estimate.fetch_slots,
        max_requests=MAX_FINAL_BATCH_REQUESTS,
        request_cap=MAX_FINAL_BATCH_REQUESTS,
        allowed_leagues=OOS_LEAGUES,
    )
    ordered = sorted(estimate.fetch_slots, key=lambda item: (item.league, item.sport_key or "", item.as_of))
    for previous, current in zip(ordered, ordered[1:], strict=False):
        same_key = (previous.league, previous.sport_key) == (current.league, current.sport_key)
        if same_key and current.as_of - previous.as_of < timedelta(hours=12):
            raise ValidationError(
                "persist_cadence",
                f"Refusing sub-daily historical cadence for {previous.league}.",
            )
    remaining_before: int | None = None
    remaining_after: int | None = None
    catalog_keys: list[str] = []
    include_qualification = True
    if probe_quota and not estimate_only:
        sports, headers = provider.sports_catalog()
        catalog_keys = [str(item.get("key") or "") for item in sports if item.get("key")]
        remaining_before = parse_odds_quota(headers).requests_remaining
        if any(item.sport_key == CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY for item in estimate.fetch_slots):
            if CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY not in catalog_keys:
                include_qualification = False
                estimate.qualification_unavailable = True
        planned_credits = estimate.estimated_credits
        if not include_qualification:
            remaining = [
                item
                for item in estimate.fetch_slots
                if item.sport_key != CHAMPIONS_LEAGUE_QUALIFICATION_SPORT_KEY
            ]
            planned_credits = len(remaining) * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
        if remaining_before is not None and remaining_before < planned_credits:
            raise ValidationError(
                "persist_cap",
                f"Remaining Odds API credits ({remaining_before}) cannot cover the planned "
                f"{planned_credits} credits. Stopping before historical requests.",
            )
    replay_payload: dict[str, object] = {
        "payloads": estimate.replay_payload_count,
        "records_accepted": 0,
        "duplicates": 0,
        "quarantined": 0,
    }
    if estimate_only:
        return FinalBatchReport(
            estimate=estimate,
            persist=None,
            replay=replay_payload,
            coverage_before=coverage_before or {},
            coverage_after=coverage_before or {},
            dry_run=pipeline._dry_run,
            estimate_only=True,
            credits_planned=estimate.estimated_credits,
            credits_consumed=0,
            credits_remaining_before=remaining_before,
            credits_remaining_after=remaining_before,
            counts_before=counts_before or {},
            counts_after=counts_before or {},
            sports_catalog_keys=catalog_keys,
            requests_executed=0,
            requests_skipped=len(estimate.fetch_slots),
            isolation=_isolation_counts(counts_before or {}),
        )
    replay_report: IngestionReport | None = None
    if raw_root is not None and estimate.replay_payload_count:
        stored = load_historical_stored_raw(raw_root, sport_keys=frozenset(estimate.replay_sport_keys))
        replay_report = pipeline.reprocess_stored(
            stored,
            provider_name=LIVE_ODDS_PROVIDER,
            resource=ResourceType.ODDS,
        )
        replay_payload = {
            "payloads": len(stored),
            "records_accepted": replay_report.records_accepted,
            "duplicates": replay_report.duplicates,
            "quarantined": len(replay_report.quarantined),
        }
    active_estimate = estimate
    if engine is not None:
        active_estimate = estimate_final_oos_odds_batch(
            engine=engine,
            parquet_path=parquet_path or DEFAULT_PARQUET_PATH,
            existing_request_keys=estimate.existing_request_keys,
            raw_root=raw_root,
            replay_payload_count=estimate.replay_payload_count,
            include_qualification=include_qualification,
        )
        if active_estimate.stop_reason:
            raise ValidationError("persist_cap", active_estimate.stop_reason)
        assert_persist_scope(
            active_estimate.fetch_slots,
            max_requests=MAX_FINAL_BATCH_REQUESTS,
            request_cap=MAX_FINAL_BATCH_REQUESTS,
            allowed_leagues=OOS_LEAGUES,
        )
    persist: PersistHistoricalOddsReport | None = None
    fetch_slots = active_estimate.fetch_slots
    if fetch_slots:
        persist = run_persist_historical_odds_pilot(
            provider=provider,
            pipeline=pipeline,
            matches=active_estimate.matches,
            slots=fetch_slots,
            max_requests=MAX_FINAL_BATCH_REQUESTS,
            strict_window=False,
            secret=secret,
            window_start=OOS_START,
            window_end=OOS_END,
            request_cap=MAX_FINAL_BATCH_REQUESTS,
            allowed_leagues=OOS_LEAGUES,
        )
        if persist.fetches:
            remaining_after = persist.fetches[-1].quota.requests_remaining
    elif remaining_before is not None:
        remaining_after = remaining_before
    counts_after = table_counts(engine) if engine is not None else {}
    coverage_after = coverage_before or {}
    if engine is not None:
        coverage_after = build_coverage_matrix(
            active_estimate.matches,
            match_odds_states(engine, active_estimate.matches),
            previously_covered=estimate.covered_match_ids,
            persist=persist,
        )
    identity = _identity_summary(persist, replay_report)
    pit = _pit_summary(engine, active_estimate.matches, persist) if engine is not None else {}
    executed = 0 if persist is None else persist.requests
    return FinalBatchReport(
        estimate=estimate,
        persist=persist,
        replay=replay_payload,
        coverage_before=coverage_before or {},
        coverage_after=coverage_after,
        dry_run=pipeline._dry_run,
        estimate_only=False,
        credits_planned=estimate.estimated_credits,
        credits_consumed=0 if persist is None else persist.credits_consumed,
        credits_remaining_before=remaining_before,
        credits_remaining_after=remaining_after,
        counts_before=counts_before or {},
        counts_after=counts_after,
        raw_payload_ids=[] if persist is None else list(persist.raw_payload_ids),
        sports_catalog_keys=catalog_keys,
        requests_executed=executed,
        requests_skipped=max(0, len(fetch_slots) - executed),
        replay_duplicates=_as_int(replay_payload.get("duplicates")),
        isolation=_isolation_counts(counts_after or counts_before or {}, pit),
        pit=pit,
        identity=identity,
    )


def write_final_batch_artefacts(
    report: FinalBatchReport,
    *,
    report_path: Path | None = None,
    doc_path: Path | None = None,
) -> dict[str, str]:
    json_file = report_path or DEFAULT_REPORT_PATH
    markdown_file = doc_path or DEFAULT_DOC_PATH
    json_file.parent.mkdir(parents=True, exist_ok=True)
    markdown_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_file.write_text(render_final_batch_markdown(report), encoding="utf-8")
    return {"report": str(json_file), "doc": str(markdown_file)}


def render_final_batch_markdown(report: FinalBatchReport) -> str:
    before = report.coverage_before
    after = report.coverage_after
    covered_before = _as_int(before.get("covered_after") or before.get("covered_before"))
    covered_after = _as_int(after.get("covered_after"), covered_before)
    newly = _as_int(after.get("newly_covered"))
    snapshots_added = _snapshots_added(report)
    competitions = after.get("by_competition") if isinstance(after.get("by_competition"), dict) else {}
    identity = report.identity
    pit = report.pit
    isolation = report.isolation
    lines = [
        "# OOS historical odds — final batch",
        "",
        "Data collection only. The frozen production OOS backtest was **not** rerun.",
        "This report measures matches with valid live PIT 1X2 odds. It does not count AI Picks, hit rate, or ROI.",
        "",
        "## Universe",
        "",
        f"{EXPECTED_OOS_MATCH_COUNT} total OOS matches",
        "",
        "## Before",
        "",
        f"matches with valid PIT odds: **{covered_before} / {EXPECTED_OOS_MATCH_COUNT}**",
        f"coverage %: **{_pct(covered_before)}**",
        "",
        "## After",
        "",
        f"matches with valid PIT odds: **{covered_after} / {EXPECTED_OOS_MATCH_COUNT}**",
        f"coverage %: **{_pct(covered_after)}**",
        "",
        "## New",
        "",
        f"newly covered matches: **{newly}**",
        f"newly persisted snapshots: **{snapshots_added}**",
        "",
        "## By competition",
        "",
        "| Competition | OOS matches | covered before | covered after | coverage % |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for slug in OOS_LEAGUES:
        bucket = competitions.get(slug) if isinstance(competitions, dict) else None
        if not isinstance(bucket, dict):
            continue
        matches_n = int(bucket.get("matches") or 0)
        before_n = int(bucket.get("covered_before") or 0)
        after_n = int(bucket.get("covered_after") or 0)
        lines.append(
            f"| {slug} | {matches_n} | {before_n} | {after_n} | {_pct(after_n, matches_n)} |"
        )
    lines.extend(
        [
            "",
            "## Requests",
            "",
            f"planned: **{len(report.estimate.fetch_slots)}**",
            f"executed: **{report.requests_executed}**",
            f"skipped: **{report.requests_skipped}**",
            f"reused: **{len(report.estimate.skipped_already_requested)}**",
            "",
            (
                "Champions League qualifying was not fetched: The Odds API `/v4/sports` "
                "catalog does not currently list `soccer_uefa_champs_league_qualification`. "
                "Existing `soccer_uefa_champs_league` snapshots were not refetched."
                if report.estimate.qualification_unavailable
                else "Champions League qualifying sport key was available and included."
            ),
            "",
            "## Credits",
            "",
            f"before: **{report.credits_remaining_before}**",
            f"consumed: **{report.credits_consumed}**",
            f"after: **{report.credits_remaining_after}**",
            "",
            "## Rejections",
            "",
            f"total events: **{identity.get('total_events', 0)}**",
            f"exact matches: **{identity.get('exact_matches', 0)}**",
            f"aliases: **{identity.get('alias_matches', 0)}**",
            f"unmatched: **{identity.get('unmatched', 0)}**",
            f"false matches: **{identity.get('false_matches', 0)}**",
            f"identity rejections: **{identity.get('identity_rejections', 0)}**",
            f"other reasons: **{identity.get('other_reasons', 0)}**",
            "",
            "## PIT",
            "",
            f"post-cutoff snapshots: **{pit.get('post_cutoff', 0)}**",
            f"post-kickoff snapshots: **{pit.get('post_kickoff', 0)}**",
            f"invalid snapshots: **{pit.get('invalid', 0)}**",
            "",
            "## Isolation",
            "",
            f"live snapshots: **{isolation.get('live_odds_snapshots', 0)}**",
            f"mock snapshots: **{isolation.get('mock_odds_snapshots', 0)}**",
            f"orphan odds: **{isolation.get('orphan_odds', 0)}**",
            "",
            "## Idempotence",
            "",
            f"duplicate snapshot IDs: **{pit.get('duplicate_snapshot_ids', 0)}**",
            (
                "duplicate persistence attempts: **"
                f"{(0 if report.persist is None else _persist_duplicates(report.persist)) + report.replay_duplicates}**"
            ),
            "",
            "Raw provider payloads were not overwritten. Duplicate persistence kept the first canonical snapshot.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _kickoff_present(kickoff: datetime, commences: list[datetime]) -> bool:
    return any(abs((item - kickoff).total_seconds()) <= KICKOFF_ALIGN_SECONDS for item in commences)


def _mls_franchise_event(match: PilotMatch, events: list[HistoricalEvent]) -> HistoricalEvent | None:
    match_home, _ = franchise_key("mls", match.home_team)
    match_away, _ = franchise_key("mls", match.away_team)
    home_set = set(mls_slugs_for_name(match.home_team))
    away_set = set(mls_slugs_for_name(match.away_team))
    if match_home not in home_set or match_away not in away_set:
        return None
    for event in events:
        if abs((event.commence_at - match.kickoff_at).total_seconds()) > KICKOFF_ALIGN_SECONDS:
            continue
        event_home, _ = franchise_key("mls", event.home_team)
        event_away, _ = franchise_key("mls", event.away_team)
        if event_home == match_home and event_away == match_away:
            return event
    return None


def _assert_oos_universe(matches: tuple[PilotMatch, ...]) -> None:
    if not matches:
        raise ValidationError("oos_window", "OOS match universe is empty.")
    unknown = sorted({item.league_slug for item in matches} - set(OOS_LEAGUES))
    if unknown:
        raise ValidationError(
            "persist_scope",
            "Final OOS odds batch only accepts the seven V1 football competitions, "
            f"not {', '.join(unknown)}.",
        )
    for match in matches:
        if match.kickoff_at < OOS_START or match.kickoff_at >= OOS_END:
            raise ValidationError(
                "oos_window",
                f"Match {match.match_id} kickoff {to_rfc3339(match.kickoff_at)} is outside the OOS window.",
            )


def _identity_summary(
    persist: PersistHistoricalOddsReport | None,
    replay: IngestionReport | None,
) -> dict[str, object]:
    total_events = 0
    exact = 0
    aliases = 0
    unmatched = 0
    false_matches = 0
    identity_rejections = 0
    other = 0
    if persist is not None:
        total_events = persist.identity.events
        exact = persist.identity.exact_matches
        aliases = persist.identity.alias_matches
        unmatched = persist.identity.rejected
        false_matches = persist.identity.false_match_count
        identity_rejections = persist.identity.rejected
    if replay is not None:
        for item in replay.quarantined:
            if item.reason_code == "unmatched_odds_event":
                unmatched += 1
                identity_rejections += 1
            elif item.reason_code == "ambiguous_identity":
                identity_rejections += 1
            else:
                other += 1
    return {
        "total_events": total_events,
        "exact_matches": exact,
        "alias_matches": aliases,
        "unmatched": unmatched,
        "false_matches": false_matches,
        "identity_rejections": identity_rejections,
        "other_reasons": other,
    }


def _pit_summary(
    engine: Engine,
    matches: tuple[PilotMatch, ...],
    persist: PersistHistoricalOddsReport | None,
) -> dict[str, object]:
    from sqlalchemy import bindparam

    ids = [item.match_id for item in matches]
    post_kickoff = 0
    duplicate_ids = 0
    orphan = 0
    if ids:
        query = text(
            """
            SELECT count(*) FILTER (WHERE o.available_at > m.kickoff_at) AS post_kickoff
            FROM odds_snapshots o
            JOIN matches m ON m.id = o.match_id
            WHERE o.match_id IN :match_ids
              AND o.source = 'the-odds-api-v4'
              AND o.data_mode = 'live'
            """
        ).bindparams(bindparam("match_ids", expanding=True))
        orphan_query = text(
            """
            SELECT count(*) FROM odds_snapshots o
            LEFT JOIN matches m ON m.id = o.match_id
            WHERE m.id IS NULL
            """
        )
        dup_query = text("SELECT count(*) FROM (SELECT id FROM odds_snapshots GROUP BY id HAVING count(*) > 1) d")
        with engine.connect() as connection:
            row = connection.execute(query, {"match_ids": ids}).one()
            post_kickoff = int(row.post_kickoff or 0)
            orphan = int(connection.execute(orphan_query).scalar_one())
            duplicate_ids = int(connection.execute(dup_query).scalar_one())
    pipeline_passed = None if persist is None else persist.pit.passed
    return {
        "post_cutoff": post_kickoff,
        "post_kickoff": post_kickoff,
        "invalid": post_kickoff,
        "duplicate_snapshot_ids": duplicate_ids,
        "orphan_odds": orphan,
        "pipeline_pit_passed": pipeline_passed,
    }


def _as_int(value: object, fallback: int = 0) -> int:
    if isinstance(value, bool) or value is None:
        return fallback
    if isinstance(value, int):
        return value
    return fallback


def _isolation_counts(counts: dict[str, int], pit: dict[str, object] | None = None) -> dict[str, int]:
    orphan = _as_int(counts.get("orphan_odds"))
    if pit is not None:
        orphan = _as_int(pit.get("orphan_odds"), orphan)
    return {
        "live_odds_snapshots": _as_int(counts.get("live_odds_snapshots")),
        "mock_odds_snapshots": _as_int(counts.get("mock_odds_snapshots")),
        "orphan_odds": orphan,
        "matches": _as_int(counts.get("matches")),
    }


def _snapshots_added(report: FinalBatchReport) -> int | None:
    before = report.counts_before.get("live_odds_snapshots")
    after = report.counts_after.get("live_odds_snapshots")
    if before is None or after is None:
        return None
    return after - before


def _persist_duplicates(persist: PersistHistoricalOddsReport) -> int:
    total = 0
    for item in persist.ingestion:
        value = item.get("duplicates")
        if isinstance(value, int):
            total += value
    return total


def _pct(part: int, whole: int = EXPECTED_OOS_MATCH_COUNT) -> str:
    if whole <= 0:
        return "0.00%"
    return f"{(part / whole) * 100:.2f}%"


def _slots_hash(slots: tuple[PersistSlot, ...]) -> str:
    encoded = json.dumps([item.to_dict() for item in slots], sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reject_secrets(payload: dict[str, object]) -> dict[str, object]:
    rendered = repr(payload).lower()
    if "apikey=" in rendered or "api_key=" in rendered:
        raise ValidationError("secret_leak", "Final OOS odds report would include an API key.")
    return payload
