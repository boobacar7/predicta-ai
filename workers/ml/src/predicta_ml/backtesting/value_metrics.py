from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

INSUFFICIENT_SAMPLE_N = 30
FIXED_STAKE = 1.0
SAMPLE_WARNING = "échantillon insuffisant pour conclure"


@dataclass(frozen=True)
class SettledBet:
    """One settled 1X2 opportunity. Stake is fixed; no commission; no push."""

    match_id: str
    selection: str
    odds: float
    edge: float
    ev: float
    kickoff_at: datetime
    outcome: str
    league: str
    profit: float
    strategy: str


def settle_decimal(*, selection: str, odds: float, outcome: str, stake: float = FIXED_STAKE) -> float:
    """Theoretical P&L for a single 1X2 unit bet. Win returns (odds-1)*stake; loss returns -stake."""

    if odds <= 1.0:
        raise ValueError("Decimal odds must be greater than 1.")
    if selection == outcome:
        return stake * (odds - 1.0)
    return -stake


def max_drawdown_units(profits: Sequence[float]) -> float:
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for profit in profits:
        equity += profit
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def strategy_metrics(bets: Sequence[SettledBet]) -> dict[str, Any]:
    n = len(bets)
    if n == 0:
        return {
            "n": 0,
            "hits": 0,
            "hit_rate": None,
            "average_odds": None,
            "average_edge": None,
            "average_ev": None,
            "theoretical_profit": 0.0,
            "theoretical_roi": None,
            "max_drawdown_units": 0.0,
            "max_drawdown_pct_of_stake": None,
            "home": 0,
            "draw": 0,
            "away": 0,
            "edge_distribution": [],
            "ev_distribution": [],
            "by_selection": {},
            "by_competition": {},
            "sample_warning": SAMPLE_WARNING,
            "stake": FIXED_STAKE,
            "stake_policy": "fixed_unit_per_opportunity",
        }
    ordered = sorted(bets, key=lambda item: (item.kickoff_at, item.match_id, item.selection))
    profits = [item.profit for item in ordered]
    hits = sum(1 for item in ordered if item.selection == item.outcome)
    profit = float(sum(profits))
    drawdown = max_drawdown_units(profits)
    by_selection = _group(ordered, lambda item: item.selection)
    by_competition = _group(ordered, lambda item: item.league)
    return {
        "n": n,
        "hits": hits,
        "hit_rate": hits / n,
        "average_odds": _mean(item.odds for item in ordered),
        "average_edge": _mean(item.edge for item in ordered),
        "average_ev": _mean(item.ev for item in ordered),
        "theoretical_profit": profit,
        "theoretical_roi": profit / (n * FIXED_STAKE),
        "max_drawdown_units": drawdown,
        "max_drawdown_pct_of_stake": drawdown / (n * FIXED_STAKE),
        "home": sum(1 for item in ordered if item.selection == "HOME"),
        "draw": sum(1 for item in ordered if item.selection == "DRAW"),
        "away": sum(1 for item in ordered if item.selection == "AWAY"),
        "edge_distribution": sorted(item.edge for item in ordered),
        "ev_distribution": sorted(item.ev for item in ordered),
        "by_selection": by_selection,
        "by_competition": by_competition,
        "sample_warning": SAMPLE_WARNING if n < INSUFFICIENT_SAMPLE_N else None,
        "stake": FIXED_STAKE,
        "stake_policy": "fixed_unit_per_opportunity",
    }


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return float(sum(items) / len(items))


def _group(bets: Sequence[SettledBet], key_fn: Callable[[SettledBet], str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[SettledBet]] = {}
    for item in bets:
        grouped.setdefault(str(key_fn(item)), []).append(item)
    report: dict[str, dict[str, Any]] = {}
    for key, items in sorted(grouped.items()):
        hits = sum(1 for item in items if item.selection == item.outcome)
        profit = float(sum(item.profit for item in items))
        n = len(items)
        report[key] = {
            "n": n,
            "hits": hits,
            "hit_rate": hits / n,
            "theoretical_roi": profit / (n * FIXED_STAKE),
            "theoretical_profit": profit,
            "sample_warning": SAMPLE_WARNING if n < INSUFFICIENT_SAMPLE_N else None,
        }
    return report
