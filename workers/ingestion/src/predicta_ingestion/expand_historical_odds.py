from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from predicta_ingestion.clock import to_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.historical_odds import (
    CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED,
    PILOT_LEAGUES,
    VALUE_SNAPSHOT_RULE,
)
from predicta_ingestion.persist_historical_odds import (
    KNOWN_IDENTITY_EXCLUSIONS,
    MIN_SLOT_GAP,
    PERSIST_CADENCE,
    PERSIST_WINDOW_END,
    PERSIST_WINDOW_START,
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
from predicta_ingestion.providers.the_odds_api import TheOddsApiProvider

# One snapshot / league / kickoff day. 40 requests × 10 credits = 400 credit hard cap.
MAX_EXPAND_REQUESTS = 40
ISOLATED_PARIS_TEAM_ID = "tm_football-sportmonks-4508"


@dataclass(frozen=True)
class ExpandWindow:
    name: str
    start: datetime
    end: datetime
    fetch: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "start": to_rfc3339(self.start),
            "end": to_rfc3339(self.end),
            "fetch": self.fetch,
        }


# Defined before scoring. Premier League + Ligue 1 only. Not chosen for ROI.
EXPAND_WINDOWS: tuple[ExpandWindow, ...] = (
    ExpandWindow(
        name="end-2025-26-may",
        start=datetime.fromisoformat("2026-05-01T00:00:00+00:00"),
        end=datetime.fromisoformat("2026-05-25T00:00:00+00:00"),
        fetch=True,
    ),
    ExpandWindow(
        name="persist-weekend-2026-08-21",
        start=PERSIST_WINDOW_START,
        end=PERSIST_WINDOW_END,
        fetch=False,
    ),
    ExpandWindow(
        name="2026-27-following-matchweeks",
        start=datetime.fromisoformat("2026-08-28T00:00:00+00:00"),
        end=datetime.fromisoformat("2026-09-07T00:00:00+00:00"),
        fetch=True,
    ),
)


@dataclass
class ExpandEstimate:
    windows: tuple[ExpandWindow, ...]
    all_matches: tuple[PilotMatch, ...]
    fetch_matches: tuple[PilotMatch, ...]
    reuse_matches: tuple[PilotMatch, ...]
    planned_slots: tuple[PersistSlot, ...]
    skipped_already_persisted: tuple[PersistSlot, ...]
    fetch_slots: tuple[PersistSlot, ...]
    documented_credits_per_request: int = CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    estimated_credits: int = 0
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "windows": [item.to_dict() for item in self.windows],
            "leagues": list(PILOT_LEAGUES),
            "cadence": PERSIST_CADENCE,
            "value_snapshot_rule": VALUE_SNAPSHOT_RULE,
            "all_matches": len(self.all_matches),
            "fetch_matches": len(self.fetch_matches),
            "reuse_matches": len(self.reuse_matches),
            "planned_slots": len(self.planned_slots),
            "skipped_already_persisted": [item.to_dict() for item in self.skipped_already_persisted],
            "fetch_slots": [item.to_dict() for item in self.fetch_slots],
            "requests": len(self.fetch_slots),
            "documented_credits_per_request": self.documented_credits_per_request,
            "estimated_credits": self.estimated_credits,
            "max_expand_requests": MAX_EXPAND_REQUESTS,
            "stop_reason": self.stop_reason,
            "known_identity_exclusions": dict(KNOWN_IDENTITY_EXCLUSIONS),
            "isolated_paris_team_id": ISOLATED_PARIS_TEAM_ID,
        }


@dataclass
class ExpandHistoricalOddsReport:
    estimate: ExpandEstimate
    persist: PersistHistoricalOddsReport | None
    dry_run: bool
    estimate_only: bool
    credits_planned: int
    credits_consumed: int | None
    raw_payload_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        persist_payload: dict[str, object] | None = None
        if self.persist is not None:
            persist_payload = self.persist.to_dict()
        payload: dict[str, object] = {
            "kind": "expand_historical_odds_pilot",
            "estimate_only": self.estimate_only,
            "dry_run": self.dry_run,
            "credits_planned": self.credits_planned,
            "credits_consumed": self.credits_consumed,
            "credits_planned_vs_consumed": {
                "planned": self.credits_planned,
                "consumed": self.credits_consumed,
            },
            "estimate": self.estimate.to_dict(),
            "persist": persist_payload,
            "raw_payload_ids": self.raw_payload_ids,
            "cadence": PERSIST_CADENCE,
            "value_snapshot_rule": VALUE_SNAPSHOT_RULE,
            "max_expand_requests": MAX_EXPAND_REQUESTS,
        }
        return _reject_secrets(payload)


def expand_window_bounds() -> tuple[datetime, datetime]:
    starts = [item.start for item in EXPAND_WINDOWS]
    ends = [item.end for item in EXPAND_WINDOWS]
    return min(starts), max(ends)


def load_expand_matches(engine: Engine) -> tuple[PilotMatch, ...]:
    matches: list[PilotMatch] = []
    seen: set[str] = set()
    for window in EXPAND_WINDOWS:
        for match in load_matches_from_sql(engine, window_start=window.start, window_end=window.end):
            if match.match_id in seen:
                continue
            seen.add(match.match_id)
            matches.append(match)
    return tuple(sorted(matches, key=lambda item: (item.kickoff_at, item.match_id)))


def matches_for_windows(
    matches: tuple[PilotMatch, ...],
    windows: tuple[ExpandWindow, ...],
) -> tuple[PilotMatch, ...]:
    kept: list[PilotMatch] = []
    for match in matches:
        if any(window.start <= match.kickoff_at < window.end for window in windows):
            kept.append(match)
    return tuple(kept)


def match_ids_with_odds(engine: Engine, match_ids: frozenset[str]) -> frozenset[str]:
    if not match_ids:
        return frozenset()
    query = text(
        """
        SELECT DISTINCT match_id
        FROM odds_snapshots
        WHERE match_id IN :match_ids
          AND market = '1X2'
          AND source = 'the-odds-api-v4'
          AND data_mode = 'live'
        """
    ).bindparams(bindparam("match_ids", expanding=True))
    with engine.connect() as connection:
        rows = connection.execute(query, {"match_ids": list(match_ids)})
        return frozenset(str(row[0]) for row in rows)


def partition_slots(
    slots: tuple[PersistSlot, ...],
    matches: tuple[PilotMatch, ...],
    persisted_ids: frozenset[str],
) -> tuple[tuple[PersistSlot, ...], tuple[PersistSlot, ...]]:
    by_slot: dict[tuple[str, str], list[PilotMatch]] = {}
    for match in matches:
        key = (match.league_slug, match.kickoff_at.date().isoformat())
        by_slot.setdefault(key, []).append(match)
    fetch: list[PersistSlot] = []
    skipped: list[PersistSlot] = []
    for slot in slots:
        targets = by_slot.get((slot.league, slot.kickoff_date), [])
        if targets and all(item.match_id in persisted_ids for item in targets):
            skipped.append(slot)
        else:
            fetch.append(slot)
    return tuple(fetch), tuple(skipped)


def estimate_expand_run(
    *,
    engine: Engine | None = None,
    matches: tuple[PilotMatch, ...] | None = None,
    persisted_ids: frozenset[str] | None = None,
) -> ExpandEstimate:
    if matches is None:
        if engine is None:
            raise ValidationError(
                "expand_window",
                "Expanded historical odds estimate requires PostgreSQL or an explicit match universe.",
            )
        all_matches = load_expand_matches(engine)
    else:
        all_matches = matches
    fetch_windows = tuple(item for item in EXPAND_WINDOWS if item.fetch)
    reuse_windows = tuple(item for item in EXPAND_WINDOWS if not item.fetch)
    fetch_matches = matches_for_windows(all_matches, fetch_windows)
    reuse_matches = matches_for_windows(all_matches, reuse_windows)
    if not all_matches:
        raise ValidationError(
            "expand_window",
            "No Premier League / Ligue 1 matches were found in the expanded windows. "
            "Sportmonks fixtures must already exist; odds never create matches.",
        )
    unknown = {item.league_slug for item in all_matches} - set(PILOT_LEAGUES)
    if unknown:
        raise ValidationError(
            "persist_scope",
            "Expanded historical odds runner only accepts premier-league and ligue-1, "
            f"not {', '.join(sorted(unknown))}.",
        )
    planned = plan_persist_slots(fetch_matches)
    if persisted_ids is None:
        if engine is None:
            known_ids: frozenset[str] = frozenset()
        else:
            known_ids = match_ids_with_odds(engine, target_match_ids(fetch_matches))
    else:
        known_ids = persisted_ids
    fetch_slots, skipped = partition_slots(planned, fetch_matches, known_ids)
    stop_reason: str | None = None
    if len(fetch_slots) > MAX_EXPAND_REQUESTS:
        stop_reason = (
            f"Expanded window needs {len(fetch_slots)} requests which exceeds "
            f"MAX_EXPAND_REQUESTS={MAX_EXPAND_REQUESTS} "
            f"({MAX_EXPAND_REQUESTS * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED} credits). "
            "Reduce the window instead of running a silent backfill."
        )
    estimated = len(fetch_slots) * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    return ExpandEstimate(
        windows=EXPAND_WINDOWS,
        all_matches=all_matches,
        fetch_matches=fetch_matches,
        reuse_matches=reuse_matches,
        planned_slots=planned,
        skipped_already_persisted=skipped,
        fetch_slots=fetch_slots,
        estimated_credits=estimated,
        stop_reason=stop_reason,
    )


def run_expand_historical_odds_pilot(
    *,
    provider: TheOddsApiProvider,
    pipeline: IngestionPipeline,
    estimate: ExpandEstimate,
    secret: str | None = None,
    estimate_only: bool = False,
) -> ExpandHistoricalOddsReport:
    if estimate.stop_reason:
        raise ValidationError("persist_cap", estimate.stop_reason)
    assert_persist_scope(
        estimate.fetch_slots,
        max_requests=MAX_EXPAND_REQUESTS,
        request_cap=MAX_EXPAND_REQUESTS,
    )
    for previous, current in zip(
        sorted(estimate.fetch_slots, key=lambda item: (item.league, item.as_of)),
        sorted(estimate.fetch_slots, key=lambda item: (item.league, item.as_of))[1:],
        strict=False,
    ):
        if previous.league == current.league and current.as_of - previous.as_of < MIN_SLOT_GAP:
            raise ValidationError(
                "persist_cadence",
                f"Refusing sub-daily historical cadence for {previous.league}.",
            )
    if estimate_only or not estimate.fetch_slots:
        return ExpandHistoricalOddsReport(
            estimate=estimate,
            persist=None,
            dry_run=pipeline._dry_run,
            estimate_only=True if estimate_only else not bool(estimate.fetch_slots),
            credits_planned=estimate.estimated_credits,
            credits_consumed=0 if not estimate.fetch_slots else None,
            raw_payload_ids=[],
        )
    start, end = expand_window_bounds()
    persist = run_persist_historical_odds_pilot(
        provider=provider,
        pipeline=pipeline,
        matches=estimate.fetch_matches,
        slots=estimate.fetch_slots,
        max_requests=MAX_EXPAND_REQUESTS,
        strict_window=False,
        secret=secret,
        window_start=start,
        window_end=end,
        request_cap=MAX_EXPAND_REQUESTS,
    )
    return ExpandHistoricalOddsReport(
        estimate=estimate,
        persist=persist,
        dry_run=persist.dry_run,
        estimate_only=False,
        credits_planned=estimate.estimated_credits,
        credits_consumed=persist.credits_consumed,
        raw_payload_ids=list(persist.raw_payload_ids),
    )


def isolated_paris_match_ids(matches: tuple[PilotMatch, ...]) -> frozenset[str]:
    return frozenset(
        item.match_id
        for item in matches
        if item.home_team_id == ISOLATED_PARIS_TEAM_ID or item.away_team_id == ISOLATED_PARIS_TEAM_ID
    )


def _reject_secrets(payload: dict[str, object]) -> dict[str, object]:
    rendered = repr(payload).lower()
    if "apikey=" in rendered or "api_key=" in rendered:
        raise ValidationError("secret_leak", "Pilot report would include an API key.")
    return payload
