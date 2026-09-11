from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from predicta_ml.oos.odds import OddsQuote


class PublishedValueCalculator:
    """Test double of the published value-engine-0.1 identities. Production uses calculator.py."""

    def implied_probability(self, odds: Decimal) -> Decimal:
        return Decimal(1) / odds

    def no_vig_probabilities(self, odds_by_selection: dict[str, Decimal]) -> tuple[dict[str, Decimal], Decimal]:
        raw = {name: Decimal(1) / odds for name, odds in odds_by_selection.items()}
        overround = sum(raw.values(), Decimal(0))
        return {name: value / overround for name, value in raw.items()}, overround

    def edge(self, model_probability: Decimal, implied: Decimal) -> Decimal:
        return model_probability - implied

    def expected_value(self, model_probability: Decimal, odds: Decimal) -> Decimal:
        return model_probability * odds - Decimal(1)


def make_quote(
    *,
    match_id: str,
    kickoff: datetime,
    snapshot_id: str = "snap-1",
    age_hours: float = 1.0,
    home: float = 2.1,
    draw: float = 3.4,
    away: float = 3.6,
    bookmaker: str = "book-a",
) -> OddsQuote:
    available = kickoff - timedelta(hours=age_hours)
    return OddsQuote(
        snapshot_id=snapshot_id,
        match_id=match_id,
        provider="the-odds-api-v4",
        bookmaker=bookmaker,
        market="1X2",
        available_at=available,
        collected_at=available,
        home_odds=home,
        draw_odds=draw,
        away_odds=away,
        data_mode="live",
    )


def utc(year: int, month: int, day: int, hour: int = 15) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)
