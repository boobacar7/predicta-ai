from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from predicta_ml.oos.errors import OosIdentityError, OosLeakageError, OosProtocolError
from predicta_ml.oos.protocol import ODDS_SELECTION_POLICY


@dataclass(frozen=True)
class OddsQuote:
    snapshot_id: str
    match_id: str
    provider: str
    bookmaker: str
    market: str
    available_at: datetime
    collected_at: datetime
    home_odds: float
    draw_odds: float
    away_odds: float
    data_mode: str

    @property
    def is_complete_1x2(self) -> bool:
        return min(self.home_odds, self.draw_odds, self.away_odds) > 1.0


def assert_odds_pit_safe(quote: OddsQuote, *, cutoff_at: datetime, kickoff_at: datetime) -> None:
    available = quote.available_at.astimezone(UTC)
    cutoff = cutoff_at.astimezone(UTC)
    kickoff = kickoff_at.astimezone(UTC)
    if available > cutoff:
        raise OosLeakageError(
            f"Odds snapshot {quote.snapshot_id} available_at {available.isoformat()} "
            f"is after cutoff {cutoff.isoformat()}."
        )
    if available > kickoff:
        raise OosLeakageError(
            f"Odds snapshot {quote.snapshot_id} is post-kickoff ({kickoff.isoformat()})."
        )
    if quote.market != "1X2":
        raise OosProtocolError(f"Odds snapshot {quote.snapshot_id} is not a 1X2 market.")
    if not quote.is_complete_1x2:
        raise OosProtocolError(f"Odds snapshot {quote.snapshot_id} is an incomplete 1X2 market.")


def assert_no_snapshot_ambiguity(quotes: tuple[OddsQuote, ...]) -> None:
    by_id: dict[str, OddsQuote] = {}
    by_key: dict[tuple[str, datetime, datetime], OddsQuote] = {}
    for quote in quotes:
        previous = by_id.get(quote.snapshot_id)
        if previous is not None and previous != quote:
            raise OosIdentityError(f"Duplicate odds snapshot id with different payload: {quote.snapshot_id}")
        by_id[quote.snapshot_id] = quote
        key = (quote.match_id, quote.available_at, quote.collected_at)
        existing = by_key.get(key)
        if existing is not None and existing != quote:
            raise OosIdentityError(
                "Duplicate odds snapshots share (match_id, available_at, collected_at) "
                f"but disagree: {existing.snapshot_id} vs {quote.snapshot_id}."
            )
        by_key[key] = quote


def select_pit_snapshot(
    quotes: tuple[OddsQuote, ...],
    *,
    match_id: str,
    cutoff_at: datetime,
    kickoff_at: datetime,
) -> OddsQuote:
    """Last complete 1X2 snapshot with available_at <= cutoff.

    This is the published OddsService / value-engine-0.1 policy. Production
    scoring must still call OddsService; this helper exists so leakage tests
    can fail closed without a second formula stack.
    """

    assert_no_snapshot_ambiguity(quotes)
    eligible = tuple(item for item in quotes if item.match_id == match_id and item.available_at <= cutoff_at)
    if not eligible:
        future = tuple(item for item in quotes if item.match_id == match_id and item.available_at > cutoff_at)
        if future:
            raise OosLeakageError(
                f"Only post-cutoff odds exist for {match_id}; refusing to select a future snapshot."
            )
        raise OosProtocolError(f"No odds snapshot is available for {match_id} at cutoff.")
    complete = tuple(item for item in eligible if item.is_complete_1x2)
    ordered = sorted(complete or eligible, key=lambda item: (item.available_at, item.collected_at, item.snapshot_id))
    selected = ordered[-1]
    assert_odds_pit_safe(selected, cutoff_at=cutoff_at, kickoff_at=kickoff_at)
    if selected.available_at > cutoff_at:
        raise OosLeakageError("Selected odds snapshot is in the future of cutoff.")
    return selected


def odds_age_seconds(quote: OddsQuote, cutoff_at: datetime) -> float:
    return (cutoff_at.astimezone(UTC) - quote.available_at.astimezone(UTC)).total_seconds()


def published_odds_policy() -> str:
    return ODDS_SELECTION_POLICY
