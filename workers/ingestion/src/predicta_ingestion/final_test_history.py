from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from predicta_ingestion.clock import to_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.expand_historical_odds import (
    ISOLATED_PARIS_TEAM_ID,
    ExpandEstimate,
    ExpandHistoricalOddsReport,
    ExpandWindow,
    isolated_paris_match_ids,
    match_ids_with_odds,
    matches_for_windows,
    partition_slots,
)
from predicta_ingestion.historical_odds import (
    CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED,
    PILOT_LEAGUES,
    VALUE_SNAPSHOT_RULE,
)
from predicta_ingestion.persist_historical_odds import (
    KNOWN_IDENTITY_EXCLUSIONS,
    MIN_SLOT_GAP,
    PERSIST_CADENCE,
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

# Official Elo partitions — copied for documentation only. Not modified.
ELO_FINAL_TRAIN_END = datetime(2026, 1, 1, tzinfo=UTC)
ELO_CALIBRATION_FIT_END = datetime(2026, 5, 1, tzinfo=UTC)
ELO_FINAL_TEST_START = datetime(2026, 7, 1, tzinfo=UTC)

# 120 requests × 10 credits = 1200 credit hard cap. Not a 5-minute backfill.
MAX_FINAL_TEST_REQUESTS = 120
FINAL_TEST_HISTORY_KIND = "expand_final_test_history"
WINDOWS_ARTEFACT_VERSION = "final-test-windows-v1"


@dataclass(frozen=True)
class FinalTestWindow:
    """Evaluation window defined before scoring. Dates are not chosen from ROI."""

    window_id: str
    name: str
    start: datetime
    end: datetime
    fetch: bool
    rationale: str
    elo_temporal_split: str
    additional: bool

    def to_expand_window(self) -> ExpandWindow:
        return ExpandWindow(name=self.window_id, start=self.start, end=self.end, fetch=self.fetch)

    def to_dict(self) -> dict[str, object]:
        return {
            "window_id": self.window_id,
            "name": self.name,
            "start": to_rfc3339(self.start),
            "end": to_rfc3339(self.end),
            "fetch": self.fetch,
            "rationale": self.rationale,
            "elo_temporal_split": self.elo_temporal_split,
            "additional": self.additional,
        }


# Frozen before any scoring. Premier League + Ligue 1 only.
# Additional windows sit entirely before fold_1 validation (2025-01-01) so they
# are not a silent requalification of calibration_select / calibration_fit /
# walk-forward validation. Official Elo temporal_split remains final_train.
# The existing Aug–Sep 2026 official final_test is reused, never refetched.
FINAL_TEST_WINDOWS: tuple[FinalTestWindow, ...] = (
    FinalTestWindow(
        window_id="final_test_window_01",
        name="2024-25-opening",
        start=datetime(2024, 8, 16, tzinfo=UTC),
        end=datetime(2024, 10, 1, tzinfo=UTC),
        fetch=True,
        additional=True,
        elo_temporal_split="final_train",
        rationale=(
            "Earliest Premier League + Ligue 1 Sportmonks block in PostgreSQL "
            "(2024-25 opening matchweeks). Consecutive finished fixtures. "
            "Same calendar phase as the current Aug–Sep 2026 official final_test. "
            "Odds API historical coverage starts 2020-06-06. Not used for Elo "
            "calibration_select. Defined from volume and data availability, not ROI."
        ),
    ),
    FinalTestWindow(
        window_id="final_test_window_02",
        name="2024-25-autumn",
        start=datetime(2024, 10, 1, tzinfo=UTC),
        end=datetime(2024, 12, 1, tzinfo=UTC),
        fetch=True,
        additional=True,
        elo_temporal_split="final_train",
        rationale=(
            "Next consecutive PL + Ligue 1 matchweeks after window 01. "
            "Independent autumn block, no overlap with window 01 or May 2026. "
            "All matches finished in Sportmonks. Defined before scoring."
        ),
    ),
    FinalTestWindow(
        window_id="final_test_window_03",
        name="2024-25-december",
        start=datetime(2024, 12, 1, tzinfo=UTC),
        end=datetime(2025, 1, 1, tzinfo=UTC),
        fetch=True,
        additional=True,
        elo_temporal_split="final_train",
        rationale=(
            "Next consecutive block, ending exactly at Elo FINAL_TRAIN_END / "
            "fold_1 validation start (exclusive). Stops before model-selection "
            "windows. Festive Premier League congestion is the real calendar, "
            "not a ROI filter. Defined before scoring."
        ),
    ),
    FinalTestWindow(
        window_id="final_test_window_existing",
        name="existing-official-final-test-2026-08-09",
        start=datetime(2026, 8, 21, tzinfo=UTC),
        end=datetime(2026, 9, 7, tzinfo=UTC),
        fetch=False,
        additional=False,
        elo_temporal_split="final_test",
        rationale=(
            "Already persisted official Elo final_test (weekend 21–24 Aug 2026 "
            "+ following matchweeks through 6 Sep). Reused for comparison. "
            "Zero fetch. Not counted toward the additional 300–500 target."
        ),
    ),
)


# Periods with Sportmonks PL+L1 volume that were NOT selected, and why.
# Documented so another agent can reconstruct the universe without guessing.
EXCLUDED_PERIODS: tuple[dict[str, str], ...] = (
    {
        "name": "fold_1_validation",
        "start": "2025-01-01T00:00:00Z",
        "end": "2025-07-01T00:00:00Z",
        "reason": (
            "Walk-forward fold_1 validation used for Elo K / home-advantage selection. "
            "Not requalified as final_test."
        ),
    },
    {
        "name": "fold_2_validation_including_2025-26-opening",
        "start": "2025-07-01T00:00:00Z",
        "end": "2026-01-01T00:00:00Z",
        "reason": (
            "Walk-forward fold_2 validation (includes Aug–Sep 2025, the calendar analog "
            "of current final_test). Not requalified as final_test."
        ),
    },
    {
        "name": "calibration_fit",
        "start": "2026-01-01T00:00:00Z",
        "end": "2026-05-01T00:00:00Z",
        "reason": "Elo calibration_fit. Not requalified as final_test.",
    },
    {
        "name": "calibration_select_may_2026",
        "start": "2026-05-01T00:00:00Z",
        "end": "2026-07-01T00:00:00Z",
        "reason": "Elo calibration_select (already scored in the expanded pilot). Not requalified as final_test.",
    },
    {
        "name": "official_final_test_unfinished_after_2026-09-07",
        "start": "2026-09-07T00:00:00Z",
        "end": "2026-09-12T00:00:00Z",
        "reason": (
            "Official Elo final_test remainder. Zero additional finished PL+L1 matches "
            "in Sportmonks at freeze time (Rennes-OM 2026-09-11 still scheduled)."
        ),
    },
)


def elo_temporal_split(kickoff_at: datetime) -> str:
    """Official Elo partition. Never rewritten by this expansion."""

    if kickoff_at < ELO_FINAL_TRAIN_END:
        return "final_train"
    if kickoff_at < ELO_CALIBRATION_FIT_END:
        return "calibration_fit"
    if kickoff_at < ELO_FINAL_TEST_START:
        return "calibration_select"
    return "final_test"


def window_for_kickoff(kickoff_at: datetime) -> FinalTestWindow | None:
    for window in FINAL_TEST_WINDOWS:
        if window.start <= kickoff_at < window.end:
            return window
    return None


def as_expand_windows(windows: tuple[FinalTestWindow, ...] | None = None) -> tuple[ExpandWindow, ...]:
    source = windows if windows is not None else FINAL_TEST_WINDOWS
    return tuple(item.to_expand_window() for item in source)


def fetch_window_bounds(windows: tuple[FinalTestWindow, ...] | None = None) -> tuple[datetime, datetime]:
    source = [item for item in (windows or FINAL_TEST_WINDOWS) if item.fetch]
    if not source:
        raise ValidationError("final_test_window", "No fetch windows were defined.")
    return min(item.start for item in source), max(item.end for item in source)


def load_final_test_matches(
    engine: Engine,
    *,
    windows: tuple[FinalTestWindow, ...] | None = None,
) -> tuple[PilotMatch, ...]:
    matches: list[PilotMatch] = []
    seen: set[str] = set()
    for window in windows or FINAL_TEST_WINDOWS:
        for match in load_matches_from_sql(engine, window_start=window.start, window_end=window.end):
            if match.match_id in seen:
                continue
            seen.add(match.match_id)
            matches.append(match)
    return tuple(sorted(matches, key=lambda item: (item.kickoff_at, item.match_id)))


def windows_artefact() -> dict[str, object]:
    """Versioned window definition. Contains no ROI and is safe to commit before scoring."""

    return {
        "artefact_version": WINDOWS_ARTEFACT_VERSION,
        "kind": FINAL_TEST_HISTORY_KIND,
        "defined_before_scoring": True,
        "selection_criterion": (
            "Sportmonks availability, The Odds API historical coverage from 2020-06-06, "
            "finished PL+Ligue 1 volume, consecutive matchweeks, distance from Elo "
            "calibration_select / calibration_fit / walk-forward validation, "
            "and no overlap with already-scored May 2026 or Aug–Sep 2026 fetch windows. "
            "Windows were not chosen by observing ROI."
        ),
        "competitions": list(PILOT_LEAGUES),
        "market": "h2h",
        "canonical_market": "1X2",
        "region": "eu",
        "cadence": PERSIST_CADENCE,
        "value_snapshot_rule": VALUE_SNAPSHOT_RULE,
        "max_requests": MAX_FINAL_TEST_REQUESTS,
        "credits_per_request": CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED,
        "elo_partitions_unmodified": {
            "FINAL_TRAIN_END": to_rfc3339(ELO_FINAL_TRAIN_END),
            "CALIBRATION_FIT_END": to_rfc3339(ELO_CALIBRATION_FIT_END),
            "FINAL_TEST_START": to_rfc3339(ELO_FINAL_TEST_START),
        },
        "windows": [item.to_dict() for item in FINAL_TEST_WINDOWS],
        "excluded_periods": list(EXCLUDED_PERIODS),
        "known_identity_exclusions": dict(KNOWN_IDENTITY_EXCLUSIONS),
        "isolated_paris_team_id": ISOLATED_PARIS_TEAM_ID,
    }


def estimate_final_test_run(
    *,
    engine: Engine | None = None,
    matches: tuple[PilotMatch, ...] | None = None,
    persisted_ids: frozenset[str] | None = None,
    windows: tuple[FinalTestWindow, ...] | None = None,
) -> ExpandEstimate:
    active_windows = windows or FINAL_TEST_WINDOWS
    expand_windows = as_expand_windows(active_windows)
    if matches is None:
        if engine is None:
            raise ValidationError(
                "final_test_window",
                "Final-test history estimate requires PostgreSQL or an explicit match universe.",
            )
        all_matches = load_final_test_matches(engine, windows=active_windows)
    else:
        all_matches = matches
    fetch_windows = tuple(item for item in expand_windows if item.fetch)
    reuse_windows = tuple(item for item in expand_windows if not item.fetch)
    fetch_matches = matches_for_windows(all_matches, fetch_windows)
    reuse_matches = matches_for_windows(all_matches, reuse_windows)
    if not all_matches:
        raise ValidationError(
            "final_test_window",
            "No Premier League / Ligue 1 matches were found in the final-test windows. "
            "Sportmonks fixtures must already exist; odds never create matches.",
        )
    unknown = {item.league_slug for item in all_matches} - set(PILOT_LEAGUES)
    if unknown:
        raise ValidationError(
            "persist_scope",
            "Final-test history runner only accepts premier-league and ligue-1, "
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
    if len(fetch_slots) > MAX_FINAL_TEST_REQUESTS:
        stop_reason = (
            f"Final-test windows need {len(fetch_slots)} requests which exceeds "
            f"MAX_FINAL_TEST_REQUESTS={MAX_FINAL_TEST_REQUESTS} "
            f"({MAX_FINAL_TEST_REQUESTS * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED} credits). "
            "Reduce the window instead of running a silent backfill."
        )
    estimated = len(fetch_slots) * CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED
    return ExpandEstimate(
        windows=expand_windows,
        all_matches=all_matches,
        fetch_matches=fetch_matches,
        reuse_matches=reuse_matches,
        planned_slots=planned,
        skipped_already_persisted=skipped,
        fetch_slots=fetch_slots,
        estimated_credits=estimated,
        stop_reason=stop_reason,
    )


def run_expand_final_test_history(
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
        max_requests=MAX_FINAL_TEST_REQUESTS,
        request_cap=MAX_FINAL_TEST_REQUESTS,
    )
    ordered = sorted(estimate.fetch_slots, key=lambda item: (item.league, item.as_of))
    for previous, current in zip(ordered, ordered[1:], strict=False):
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
            credits_consumed=0 if estimate_only or not estimate.fetch_slots else None,
            raw_payload_ids=[],
        )
    start, end = fetch_window_bounds()
    persist = run_persist_historical_odds_pilot(
        provider=provider,
        pipeline=pipeline,
        matches=estimate.fetch_matches,
        slots=estimate.fetch_slots,
        max_requests=MAX_FINAL_TEST_REQUESTS,
        strict_window=False,
        secret=secret,
        window_start=start,
        window_end=end,
        request_cap=MAX_FINAL_TEST_REQUESTS,
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


def report_payload(report: ExpandHistoricalOddsReport) -> dict[str, object]:
    payload = report.to_dict()
    payload["kind"] = FINAL_TEST_HISTORY_KIND
    payload["windows_artefact"] = windows_artefact()
    payload["max_final_test_requests"] = MAX_FINAL_TEST_REQUESTS
    payload["max_expand_requests"] = MAX_FINAL_TEST_REQUESTS
    return payload


def assert_windows_are_predeclared() -> None:
    ids = [item.window_id for item in FINAL_TEST_WINDOWS]
    if len(ids) != len(set(ids)):
        raise ValidationError("final_test_window", "Window identifiers must be unique.")
    additional = [item for item in FINAL_TEST_WINDOWS if item.additional]
    if not additional:
        raise ValidationError("final_test_window", "At least one additional window is required.")
    for window in additional:
        if window.end > ELO_FINAL_TRAIN_END:
            raise ValidationError(
                "final_test_window",
                f"{window.window_id} crosses Elo FINAL_TRAIN_END; refusing to requalify "
                "calibration or model-selection periods as final_test.",
            )
        if window.elo_temporal_split != "final_train":
            raise ValidationError(
                "final_test_window",
                f"{window.window_id} additional window must keep elo_temporal_split=final_train.",
            )
        if window.start >= window.end:
            raise ValidationError("final_test_window", f"{window.window_id} has empty bounds.")
    for left, right in zip(FINAL_TEST_WINDOWS, FINAL_TEST_WINDOWS[1:], strict=False):
        if left.window_id == "final_test_window_existing" or right.window_id == "final_test_window_existing":
            continue
        if left.end > right.start:
            raise ValidationError(
                "final_test_window",
                f"{left.window_id} overlaps {right.window_id}.",
            )


assert_windows_are_predeclared()

# Re-export helpers tests and CLI already use.
__all__ = [
    "ELO_CALIBRATION_FIT_END",
    "ELO_FINAL_TEST_START",
    "ELO_FINAL_TRAIN_END",
    "EXCLUDED_PERIODS",
    "FINAL_TEST_HISTORY_KIND",
    "FINAL_TEST_WINDOWS",
    "ISOLATED_PARIS_TEAM_ID",
    "MAX_FINAL_TEST_REQUESTS",
    "WINDOWS_ARTEFACT_VERSION",
    "ExpandEstimate",
    "ExpandHistoricalOddsReport",
    "FinalTestWindow",
    "PersistSlot",
    "PilotMatch",
    "as_expand_windows",
    "elo_temporal_split",
    "estimate_final_test_run",
    "fetch_window_bounds",
    "isolated_paris_match_ids",
    "load_final_test_matches",
    "match_ids_with_odds",
    "report_payload",
    "run_expand_final_test_history",
    "target_match_ids",
    "window_for_kickoff",
    "windows_artefact",
]
