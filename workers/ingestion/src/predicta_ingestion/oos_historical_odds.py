from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from predicta_ingestion.clock import to_rfc3339
from predicta_ingestion.config import PACKAGE_ROOT
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.expand_historical_odds import ISOLATED_PARIS_TEAM_ID
from predicta_ingestion.historical_odds import (
    CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED,
    VALUE_SNAPSHOT_RULE,
    parse_odds_quota,
)
from predicta_ingestion.persist_historical_odds import (
    KNOWN_IDENTITY_EXCLUSIONS,
    MIN_SLOT_GAP,
    PERSIST_CADENCE,
    PersistHistoricalOddsReport,
    PersistSlot,
    PilotMatch,
    assert_persist_scope,
    load_matches_from_sql,
    plan_persist_slots,
    run_persist_historical_odds_pilot,
    target_match_ids,
)
from predicta_ingestion.pipeline import IngestionPipeline
from predicta_ingestion.providers.leagues import V1_FOOTBALL_LEAGUES
from predicta_ingestion.providers.the_odds_api import (
    DEFAULT_MARKETS,
    DEFAULT_REGIONS,
    LIVE_ODDS_PROVIDER,
    LIVE_ODDS_SOURCE,
    V1_LEAGUE_SPORT_KEYS,
    TheOddsApiProvider,
)

# Frozen true-OOS window. Must match docs/ml/production-oos-protocol.md.
OOS_START = datetime(2026, 7, 1, tzinfo=UTC)
OOS_END = datetime(2026, 9, 10, 2, 30, 1, tzinfo=UTC)
OOS_DATASET_VERSION = "football-1x2-history-0.3"
EXPECTED_OOS_MATCH_COUNT = 387
OOS_LEAGUES: tuple[str, ...] = tuple(item.slug for item in V1_FOOTBALL_LEAGUES)
OOS_HISTORY_KIND = "expand_oos_historical_odds"
# 80 uncovered league-days + small buffer. Not a silent backfill.
MAX_OOS_REQUESTS = 85
DEFAULT_PARQUET_PATH = PACKAGE_ROOT / "var" / "football-1x2-history.parquet"
REPO_ROOT = PACKAGE_ROOT.parent.parent
DEFAULT_COVERAGE_PATH = REPO_ROOT / "workers" / "ml" / "reports" / "oos-odds-coverage.json"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "workers" / "ml" / "reports" / "oos-odds-expansion-manifest.json"


@dataclass(frozen=True)
class MatchOddsState:
    match_id: str
    snapshot_count: int
    earliest_available_at: datetime | None
    latest_available_at: datetime | None
    pre_kickoff_count: int

    @property
    def has_valid_pre_match(self) -> bool:
        return self.pre_kickoff_count > 0


@dataclass
class OosOddsEstimate:
    matches: tuple[PilotMatch, ...]
    planned_slots: tuple[PersistSlot, ...]
    skipped_already_persisted: tuple[PersistSlot, ...]
    skipped_already_requested: tuple[PersistSlot, ...]
    skipped_identity_only: tuple[PersistSlot, ...]
    coalesced_slots: tuple[PersistSlot, ...]
    fetch_slots: tuple[PersistSlot, ...]
    covered_match_ids: frozenset[str]
    reusable_match_ids: frozenset[str]
    fetch_match_ids: frozenset[str]
    isolated_match_ids: frozenset[str]
    existing_request_keys: frozenset[str]
    documented_credits_per_request: int = CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    estimated_credits: int = 0
    stop_reason: str | None = None
    plan_sha256: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": OOS_HISTORY_KIND,
            "oos_start": to_rfc3339(OOS_START),
            "oos_end": to_rfc3339(OOS_END),
            "competitions": list(OOS_LEAGUES),
            "market": DEFAULT_MARKETS,
            "canonical_market": "1X2",
            "region": DEFAULT_REGIONS,
            "provider": LIVE_ODDS_PROVIDER,
            "source": LIVE_ODDS_SOURCE,
            "cadence": PERSIST_CADENCE,
            "value_snapshot_rule": VALUE_SNAPSHOT_RULE,
            "all_matches": len(self.matches),
            "covered_matches": len(self.reusable_match_ids),
            "fetch_matches": len(self.fetch_match_ids),
            "isolated_matches": len(self.isolated_match_ids),
            "planned_slots": len(self.planned_slots),
            "skipped_already_persisted": [item.to_dict() for item in self.skipped_already_persisted],
            "skipped_already_requested": [item.to_dict() for item in self.skipped_already_requested],
            "skipped_identity_only": [item.to_dict() for item in self.skipped_identity_only],
            "coalesced_slots": [item.to_dict() for item in self.coalesced_slots],
            "fetch_slots": [item.to_dict() for item in self.fetch_slots],
            "requests": len(self.fetch_slots),
            "documented_credits_per_request": self.documented_credits_per_request,
            "estimated_credits": self.estimated_credits,
            "max_oos_requests": MAX_OOS_REQUESTS,
            "existing_request_keys": len(self.existing_request_keys),
            "plan_sha256": self.plan_sha256,
            "stop_reason": self.stop_reason,
            "known_identity_exclusions": dict(KNOWN_IDENTITY_EXCLUSIONS),
            "isolated_paris_team_id": ISOLATED_PARIS_TEAM_ID,
        }


@dataclass
class OosOddsExpansionReport:
    estimate: OosOddsEstimate
    persist: PersistHistoricalOddsReport | None
    coverage: dict[str, object]
    dry_run: bool
    estimate_only: bool
    credits_planned: int
    credits_consumed: int | None
    credits_remaining_before: int | None = None
    credits_remaining_after: int | None = None
    counts_before: dict[str, int] = field(default_factory=dict)
    counts_after: dict[str, int] = field(default_factory=dict)
    raw_payload_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        persist_payload: dict[str, object] | None = None
        if self.persist is not None:
            persist_payload = self.persist.to_dict()
        payload: dict[str, object] = {
            "kind": OOS_HISTORY_KIND,
            "estimate_only": self.estimate_only,
            "dry_run": self.dry_run,
            "credits_planned": self.credits_planned,
            "credits_consumed": self.credits_consumed,
            "credits_remaining_before": self.credits_remaining_before,
            "credits_remaining_after": self.credits_remaining_after,
            "additional_credits_consumed": self.credits_consumed,
            "counts_before": dict(self.counts_before),
            "counts_after": dict(self.counts_after),
            "credits_planned_vs_consumed": {
                "planned": self.credits_planned,
                "consumed": self.credits_consumed,
            },
            "estimate": self.estimate.to_dict(),
            "persist": persist_payload,
            "coverage": self.coverage,
            "raw_payload_ids": self.raw_payload_ids,
            "cadence": PERSIST_CADENCE,
            "value_snapshot_rule": VALUE_SNAPSHOT_RULE,
            "max_oos_requests": MAX_OOS_REQUESTS,
        }
        return _reject_secrets(payload)


def historical_request_key(
    league: str,
    as_of: datetime,
    *,
    regions: str = DEFAULT_REGIONS,
    sport_key: str | None = None,
) -> str:
    mapped = sport_key or V1_LEAGUE_SPORT_KEYS.get(league)
    if mapped is None:
        raise ValidationError("unknown_league", f"No The Odds API sport key is mapped for '{league}'.")
    return f"the_odds_api:historical_odds:{mapped}:{regions}:{DEFAULT_MARKETS}:{to_rfc3339(as_of)}"


def existing_historical_request_keys(raw_root: Path) -> frozenset[str]:
    keys: set[str] = set()
    if not raw_root.is_dir():
        return frozenset()
    for path in raw_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        key = payload.get("request_key")
        if isinstance(key, str) and ":historical_odds:" in key:
            keys.add(key)
    return frozenset(keys)


def load_oos_match_ids_from_parquet(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise ValidationError("oos_dataset", f"OOS parquet is missing: {path}")
    table = pq.read_table(path, columns=["match_id", "event_at", "dataset_version", "data_mode"])
    ids: list[str] = []
    versions: set[str] = set()
    modes: set[str] = set()
    for match_id, event_at, dataset_version, data_mode in zip(
        table.column("match_id").to_pylist(),
        table.column("event_at").to_pylist(),
        table.column("dataset_version").to_pylist(),
        table.column("data_mode").to_pylist(),
        strict=True,
    ):
        kickoff = _as_utc(event_at)
        if kickoff < OOS_START or kickoff >= OOS_END:
            continue
        versions.add(str(dataset_version))
        modes.add(str(data_mode))
        ids.append(str(match_id))
    unique = tuple(dict.fromkeys(ids))
    if len(unique) != EXPECTED_OOS_MATCH_COUNT:
        raise ValidationError(
            "oos_dataset",
            f"Expected {EXPECTED_OOS_MATCH_COUNT} dataset 0.3 OOS matches, found {len(unique)}.",
        )
    if versions != {OOS_DATASET_VERSION}:
        raise ValidationError("oos_dataset", f"OOS parquet dataset_version must be {OOS_DATASET_VERSION}.")
    if modes != {"live"}:
        raise ValidationError("oos_dataset", "OOS parquet rows must be data_mode=live.")
    return unique


def isolated_oos_match_ids(matches: tuple[PilotMatch, ...]) -> frozenset[str]:
    isolated = {
        item.match_id
        for item in matches
        if item.home_team_id == ISOLATED_PARIS_TEAM_ID or item.away_team_id == ISOLATED_PARIS_TEAM_ID
    }
    isolated.update(item.match_id for item in matches if item.match_id in KNOWN_IDENTITY_EXCLUSIONS)
    return frozenset(isolated)


def load_oos_matches(
    engine: Engine,
    *,
    parquet_path: Path | None = None,
) -> tuple[PilotMatch, ...]:
    parquet_ids = load_oos_match_ids_from_parquet(parquet_path or DEFAULT_PARQUET_PATH)
    matches = load_matches_from_sql(
        engine,
        window_start=OOS_START,
        window_end=OOS_END,
        league_slugs=OOS_LEAGUES,
        match_ids=frozenset(parquet_ids),
        finished_only=True,
    )
    sql_ids = {item.match_id for item in matches}
    missing = [item for item in parquet_ids if item not in sql_ids]
    extra = sorted(sql_ids - set(parquet_ids))
    if missing or extra:
        raise ValidationError(
            "oos_identity",
            "Parquet OOS match ids and PostgreSQL ids disagree "
            f"(missing_from_sql={len(missing)}, extra_in_sql={len(extra)}). "
            "Refusing to guess match identity.",
        )
    unknown = sorted({item.league_slug for item in matches} - set(OOS_LEAGUES))
    if unknown:
        raise ValidationError(
            "persist_scope",
            "OOS historical odds runner only accepts the seven V1 football competitions, "
            f"not {', '.join(unknown)}.",
        )
    outside = [
        item.match_id
        for item in matches
        if item.kickoff_at < OOS_START or item.kickoff_at >= OOS_END
    ]
    if outside:
        raise ValidationError(
            "oos_window",
            "SQL returned matches outside the frozen OOS window; refusing to collect odds.",
        )
    return matches


def match_odds_states(engine: Engine, matches: tuple[PilotMatch, ...]) -> dict[str, MatchOddsState]:
    ids = [item.match_id for item in matches]
    empty = {
        item.match_id: MatchOddsState(
            match_id=item.match_id,
            snapshot_count=0,
            earliest_available_at=None,
            latest_available_at=None,
            pre_kickoff_count=0,
        )
        for item in matches
    }
    if not ids:
        return empty
    query = text(
        """
        SELECT o.match_id,
               count(*) AS snapshot_count,
               min(o.available_at) AS earliest,
               max(o.available_at) AS latest,
               count(*) FILTER (WHERE o.available_at <= m.kickoff_at) AS pre_kickoff_count
        FROM odds_snapshots o
        JOIN matches m ON m.id = o.match_id
        WHERE o.match_id IN :match_ids
          AND o.market = '1X2'
          AND o.source = 'the-odds-api-v4'
          AND o.data_mode = 'live'
        GROUP BY o.match_id
        """
    ).bindparams(bindparam("match_ids", expanding=True))
    with engine.connect() as connection:
        rows = connection.execute(query, {"match_ids": ids})
        for row in rows:
            empty[str(row.match_id)] = MatchOddsState(
                match_id=str(row.match_id),
                snapshot_count=int(row.snapshot_count),
                earliest_available_at=row.earliest,
                latest_available_at=row.latest,
                pre_kickoff_count=int(row.pre_kickoff_count or 0),
            )
    return empty


def table_counts(engine: Engine) -> dict[str, int]:
    query = text(
        """
        SELECT
            (SELECT count(*) FROM odds_snapshots) AS odds_snapshots,
            (SELECT count(*) FROM odds_snapshots WHERE data_mode = 'live') AS live_odds_snapshots,
            (SELECT count(*) FROM odds_snapshots WHERE data_mode = 'mock') AS mock_odds_snapshots,
            (SELECT count(*) FROM odds_selections) AS odds_selections,
            (SELECT count(*) FROM raw_payloads WHERE provider = 'the_odds_api') AS odds_raw_payloads,
            (SELECT count(*) FROM ingestion_runs WHERE provider = 'the_odds_api') AS odds_ingestion_runs,
            (SELECT count(*) FROM matches) AS matches
        """
    )
    with engine.connect() as connection:
        row = connection.execute(query).one()
        return {key: int(row._mapping[key]) for key in row._mapping}


def partition_oos_slots(
    slots: tuple[PersistSlot, ...],
    matches: tuple[PilotMatch, ...],
    *,
    covered_ids: frozenset[str],
    isolated_ids: frozenset[str],
    existing_keys: frozenset[str],
) -> tuple[tuple[PersistSlot, ...], tuple[PersistSlot, ...], tuple[PersistSlot, ...], tuple[PersistSlot, ...]]:
    by_slot: dict[tuple[str, str], list[PilotMatch]] = {}
    for match in matches:
        by_slot.setdefault((match.league_slug, match.kickoff_at.date().isoformat()), []).append(match)
    fetch: list[PersistSlot] = []
    skipped_persisted: list[PersistSlot] = []
    skipped_requested: list[PersistSlot] = []
    skipped_identity: list[PersistSlot] = []
    for slot in slots:
        key = historical_request_key(slot.league, slot.as_of, sport_key=slot.sport_key)
        targets = by_slot.get((slot.league, slot.kickoff_date), [])
        actionable = [item for item in targets if item.match_id not in isolated_ids]
        if key in existing_keys:
            skipped_requested.append(slot)
            continue
        if actionable and all(item.match_id in covered_ids for item in actionable):
            skipped_persisted.append(slot)
            continue
        if targets and not actionable:
            skipped_identity.append(slot)
            continue
        if actionable and all(item.match_id in isolated_ids or item.match_id in covered_ids for item in targets):
            skipped_identity.append(slot)
            continue
        fetch.append(slot)
    return tuple(fetch), tuple(skipped_persisted), tuple(skipped_requested), tuple(skipped_identity)


def coalesce_slots(
    slots: tuple[PersistSlot, ...],
    *,
    min_gap: timedelta = MIN_SLOT_GAP,
) -> tuple[tuple[PersistSlot, ...], tuple[PersistSlot, ...]]:
    """Keep the earliest as_of when adjacent UTC days are closer than min_gap.

    MLS late kickoffs often sit just before UTC midnight; requesting the next
    day's 00:30 snapshot would be post-kickoff for the previous match. The
    earlier timestamp remains pre-match for both.
    """
    kept: list[PersistSlot] = []
    dropped: list[PersistSlot] = []
    last_by_league: dict[str, PersistSlot] = {}
    for slot in sorted(slots, key=lambda item: (item.league, item.as_of)):
        previous = last_by_league.get(slot.league)
        if previous is not None and slot.as_of - previous.as_of < min_gap:
            dropped.append(slot)
            continue
        kept.append(slot)
        last_by_league[slot.league] = slot
    return tuple(kept), tuple(dropped)


def estimate_oos_odds_run(
    *,
    engine: Engine | None = None,
    matches: tuple[PilotMatch, ...] | None = None,
    covered_ids: frozenset[str] | None = None,
    existing_request_keys: frozenset[str] | None = None,
    parquet_path: Path | None = None,
    raw_root: Path | None = None,
) -> OosOddsEstimate:
    if matches is None:
        if engine is None:
            raise ValidationError(
                "oos_window",
                "OOS historical odds estimate requires PostgreSQL or an explicit match universe.",
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
        root = raw_root if raw_root is not None else Path()
        keys = existing_historical_request_keys(root)
    planned = plan_persist_slots(all_matches, allowed_leagues=OOS_LEAGUES)
    fetch_slots, skipped_persisted, skipped_requested, skipped_identity = partition_oos_slots(
        planned,
        all_matches,
        covered_ids=known_ids,
        isolated_ids=isolated,
        existing_keys=keys,
    )
    fetch_slots, coalesced = coalesce_slots(fetch_slots)
    fetch_ids = frozenset(
        item.match_id
        for item in all_matches
        if item.match_id not in known_ids and item.match_id not in isolated
    )
    stop_reason: str | None = None
    if len(fetch_slots) > MAX_OOS_REQUESTS:
        stop_reason = (
            f"OOS window needs {len(fetch_slots)} requests which exceeds "
            f"MAX_OOS_REQUESTS={MAX_OOS_REQUESTS} "
            f"({MAX_OOS_REQUESTS * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED} credits). "
            "Reduce the request set instead of running a silent backfill."
        )
    estimated = len(fetch_slots) * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    return OosOddsEstimate(
        matches=all_matches,
        planned_slots=planned,
        skipped_already_persisted=skipped_persisted,
        skipped_already_requested=skipped_requested,
        skipped_identity_only=skipped_identity,
        coalesced_slots=coalesced,
        fetch_slots=fetch_slots,
        covered_match_ids=known_ids,
        reusable_match_ids=known_ids,
        fetch_match_ids=fetch_ids,
        isolated_match_ids=isolated,
        existing_request_keys=keys,
        estimated_credits=estimated,
        stop_reason=stop_reason,
        plan_sha256=_plan_hash(fetch_slots),
    )


def run_expand_oos_historical_odds(
    *,
    provider: TheOddsApiProvider,
    pipeline: IngestionPipeline,
    estimate: OosOddsEstimate,
    secret: str | None = None,
    estimate_only: bool = False,
    probe_quota: bool = False,
    engine: Engine | None = None,
    coverage: dict[str, object] | None = None,
    counts_before: dict[str, int] | None = None,
) -> OosOddsExpansionReport:
    if estimate.stop_reason:
        raise ValidationError("persist_cap", estimate.stop_reason)
    assert_persist_scope(
        estimate.fetch_slots,
        max_requests=MAX_OOS_REQUESTS,
        request_cap=MAX_OOS_REQUESTS,
        allowed_leagues=OOS_LEAGUES,
    )
    ordered = sorted(estimate.fetch_slots, key=lambda item: (item.league, item.as_of))
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous.league == current.league and current.as_of - previous.as_of < MIN_SLOT_GAP:
            raise ValidationError(
                "persist_cadence",
                f"Refusing sub-daily historical cadence for {previous.league}.",
            )
    remaining_before: int | None = None
    remaining_after: int | None = None
    if probe_quota and not estimate_only and estimate.fetch_slots:
        remaining_before = parse_odds_quota(provider.quota_headers()).requests_remaining
        if remaining_before is not None and remaining_before < estimate.estimated_credits:
            raise ValidationError(
                "persist_cap",
                f"Remaining Odds API credits ({remaining_before}) cannot cover the planned "
                f"{estimate.estimated_credits} credits. Stopping before historical requests.",
            )
    if estimate_only or not estimate.fetch_slots:
        return OosOddsExpansionReport(
            estimate=estimate,
            persist=None,
            coverage=coverage or {},
            dry_run=pipeline._dry_run,
            estimate_only=True if estimate_only else not bool(estimate.fetch_slots),
            credits_planned=estimate.estimated_credits,
            credits_consumed=0 if estimate_only or not estimate.fetch_slots else None,
            credits_remaining_before=remaining_before,
            credits_remaining_after=remaining_before,
            counts_before=counts_before or {},
            counts_after=counts_before or {},
            raw_payload_ids=[],
        )
    persist = run_persist_historical_odds_pilot(
        provider=provider,
        pipeline=pipeline,
        matches=estimate.matches,
        slots=estimate.fetch_slots,
        max_requests=MAX_OOS_REQUESTS,
        strict_window=False,
        secret=secret,
        window_start=OOS_START,
        window_end=OOS_END,
        request_cap=MAX_OOS_REQUESTS,
        allowed_leagues=OOS_LEAGUES,
    )
    if persist.fetches:
        remaining_after = persist.fetches[-1].quota.requests_remaining
    counts_after = table_counts(engine) if engine is not None else {}
    coverage_after = coverage
    if coverage_after is None and engine is not None:
        coverage_after = build_coverage_matrix(
            estimate.matches,
            match_odds_states(engine, estimate.matches),
            previously_covered=estimate.reusable_match_ids,
            persist=persist,
        )
    return OosOddsExpansionReport(
        estimate=estimate,
        persist=persist,
        coverage=coverage_after or {},
        dry_run=persist.dry_run,
        estimate_only=False,
        credits_planned=estimate.estimated_credits,
        credits_consumed=persist.credits_consumed,
        credits_remaining_before=remaining_before,
        credits_remaining_after=remaining_after,
        counts_before=counts_before or {},
        counts_after=counts_after,
        raw_payload_ids=list(persist.raw_payload_ids),
    )


def build_coverage_matrix(
    matches: tuple[PilotMatch, ...],
    states: dict[str, MatchOddsState],
    *,
    previously_covered: frozenset[str],
    persist: PersistHistoricalOddsReport | None = None,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    by_competition: dict[str, dict[str, int]] = {}
    newly_covered = 0
    still_uncovered = 0
    rejected: list[dict[str, object]] = []
    for match in matches:
        state = states.get(match.match_id) or MatchOddsState(match.match_id, 0, None, None, 0)
        valid = state.has_valid_pre_match
        previous = match.match_id in previously_covered
        reason = _rejection_reason(match, state, previous)
        if valid and not previous:
            newly_covered += 1
        if not valid:
            still_uncovered += 1
            rejected.append(
                {
                    "match_id": match.match_id,
                    "competition": match.league_slug,
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "kickoff_at": to_rfc3339(match.kickoff_at),
                    "rejection_reason": reason,
                }
            )
        snapshot_age = None
        if state.latest_available_at is not None and valid:
            snapshot_age = int((match.kickoff_at - state.latest_available_at).total_seconds())
        rows.append(
            {
                "competition": match.league_slug,
                "match_id": match.match_id,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "kickoff_at": to_rfc3339(match.kickoff_at),
                "existing_odds": previous,
                "historical_odds_available": state.snapshot_count > 0,
                "odds_snapshot_count": state.snapshot_count,
                "earliest_odds_available_at": (
                    None if state.earliest_available_at is None else to_rfc3339(state.earliest_available_at)
                ),
                "latest_odds_available_at": (
                    None if state.latest_available_at is None else to_rfc3339(state.latest_available_at)
                ),
                "valid_pre_match_snapshot": valid,
                "snapshot_age_seconds": snapshot_age,
                "rejection_reason": reason,
                "identity_exclusion": KNOWN_IDENTITY_EXCLUSIONS.get(match.match_id, ""),
            }
        )
        bucket = by_competition.setdefault(
            match.league_slug,
            {"matches": 0, "covered_before": 0, "covered_after": 0, "isolated": 0},
        )
        bucket["matches"] += 1
        if previous:
            bucket["covered_before"] += 1
        if valid:
            bucket["covered_after"] += 1
        if match.match_id in isolated_oos_match_ids((match,)):
            bucket["isolated"] += 1
    persist_rejections = _quarantine_by_event(persist)
    covered_after = sum(1 for item in rows if item["valid_pre_match_snapshot"])
    return {
        "oos_start": to_rfc3339(OOS_START),
        "oos_end": to_rfc3339(OOS_END),
        "matches": EXPECTED_OOS_MATCH_COUNT,
        "covered_before": len(previously_covered),
        "covered_after": covered_after,
        "newly_covered": newly_covered,
        "still_uncovered": still_uncovered,
        "coverage_before": round(len(previously_covered) / max(len(matches), 1), 6),
        "coverage_after": round(covered_after / max(len(matches), 1), 6),
        "by_competition": by_competition,
        "rows": rows,
        "rejected_events": rejected,
        "provider_quarantine_by_event": persist_rejections,
        "note": (
            "Matches with odds are not automatically eligible AI Picks. "
            "AI Picks count requires rerunning production-oos-backtest."
        ),
    }


def write_oos_odds_artefacts(
    report: OosOddsExpansionReport,
    *,
    coverage_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, str]:
    coverage_file = coverage_path or DEFAULT_COVERAGE_PATH
    manifest_file = manifest_path or DEFAULT_MANIFEST_PATH
    coverage_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    coverage_file.write_text(
        json.dumps(report.coverage, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "kind": OOS_HISTORY_KIND,
        "oos_start": to_rfc3339(OOS_START),
        "oos_end": to_rfc3339(OOS_END),
        "competitions": list(OOS_LEAGUES),
        "market": DEFAULT_MARKETS,
        "region": DEFAULT_REGIONS,
        "provider": LIVE_ODDS_PROVIDER,
        "requested_timestamps": [item.to_dict() for item in report.estimate.fetch_slots],
        "successful_requests": 0 if report.persist is None else report.persist.requests,
        "rejected_requests": (
            0
            if report.persist is None
            else len(report.estimate.fetch_slots) - report.persist.requests
        ),
        "credits_before": report.credits_remaining_before,
        "credits_after": report.credits_remaining_after,
        "additional_credits_consumed": report.credits_consumed,
        "snapshots_added": _snapshots_added(report),
        "snapshots_reused_matches": len(report.estimate.reusable_match_ids),
        "matches_newly_covered": report.coverage.get("newly_covered"),
        "matches_still_uncovered": report.coverage.get("still_uncovered"),
        "plan_sha256": report.estimate.plan_sha256,
        "dry_run": report.dry_run,
        "estimate_only": report.estimate_only,
        "counts_before": report.counts_before,
        "counts_after": report.counts_after,
    }
    manifest_file.write_text(json.dumps(_reject_secrets(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"coverage": str(coverage_file), "manifest": str(manifest_file)}


def _snapshots_added(report: OosOddsExpansionReport) -> int | None:
    before = report.counts_before.get("live_odds_snapshots")
    after = report.counts_after.get("live_odds_snapshots")
    if before is None or after is None:
        return None
    return after - before


def _rejection_reason(match: PilotMatch, state: MatchOddsState, previous: bool) -> str:
    if state.has_valid_pre_match:
        return ""
    if match.home_team_id == ISOLATED_PARIS_TEAM_ID or match.away_team_id == ISOLATED_PARIS_TEAM_ID:
        return "isolated_team: Paris / Paris FC / PSG kept distinct"
    if match.match_id in KNOWN_IDENTITY_EXCLUSIONS:
        return KNOWN_IDENTITY_EXCLUSIONS[match.match_id]
    if state.snapshot_count == 0:
        return "no_live_1x2_snapshot"
    if state.pre_kickoff_count == 0:
        return "no_valid_pre_match_snapshot"
    if previous:
        return ""
    return "unmatched_or_incomplete_odds"


def _quarantine_by_event(persist: PersistHistoricalOddsReport | None) -> dict[str, str]:
    reasons: dict[str, str] = {}
    if persist is None:
        return reasons
    for item in persist.ingestion:
        details = item.get("quarantine_details")
        if not isinstance(details, list):
            continue
        for detail in details:
            if not isinstance(detail, dict):
                continue
            event_id = str(detail.get("provider_entity_id") or "").split(":", 1)[0]
            if event_id:
                reasons[event_id] = str(detail.get("reason_code") or "quarantined")
    return reasons


def _assert_oos_universe(matches: tuple[PilotMatch, ...]) -> None:
    if not matches:
        raise ValidationError("oos_window", "OOS match universe is empty.")
    unknown = sorted({item.league_slug for item in matches} - set(OOS_LEAGUES))
    if unknown:
        raise ValidationError(
            "persist_scope",
            "OOS historical odds runner only accepts the seven V1 football competitions, "
            f"not {', '.join(unknown)}.",
        )
    for match in matches:
        if match.kickoff_at < OOS_START or match.kickoff_at >= OOS_END:
            raise ValidationError(
                "oos_window",
                f"Match {match.match_id} kickoff {to_rfc3339(match.kickoff_at)} is outside the OOS window.",
            )


def _plan_hash(slots: tuple[PersistSlot, ...]) -> str:
    payload = [item.to_dict() for item in slots]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _as_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _reject_secrets(payload: dict[str, object]) -> dict[str, object]:
    rendered = repr(payload).lower()
    if "apikey=" in rendered or "api_key=" in rendered:
        raise ValidationError("secret_leak", "OOS odds report would include an API key.")
    return payload


# Re-export for CLI/tests.
__all__ = [
    "DEFAULT_COVERAGE_PATH",
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_PARQUET_PATH",
    "EXPECTED_OOS_MATCH_COUNT",
    "MAX_OOS_REQUESTS",
    "OOS_END",
    "OOS_HISTORY_KIND",
    "OOS_LEAGUES",
    "OOS_START",
    "OosOddsEstimate",
    "OosOddsExpansionReport",
    "MatchOddsState",
    "build_coverage_matrix",
    "coalesce_slots",
    "estimate_oos_odds_run",
    "existing_historical_request_keys",
    "historical_request_key",
    "isolated_oos_match_ids",
    "load_oos_match_ids_from_parquet",
    "load_oos_matches",
    "match_odds_states",
    "run_expand_oos_historical_odds",
    "table_counts",
    "target_match_ids",
    "write_oos_odds_artefacts",
]
