from __future__ import annotations

from datetime import UTC, datetime

import pytest

from predicta_ml.backtesting.value_metrics import (
    INSUFFICIENT_SAMPLE_N,
    SAMPLE_WARNING,
    SettledBet,
    settle_decimal,
    strategy_metrics,
)


def _bet(match_id: str, selection: str, odds: float, outcome: str, kickoff: datetime) -> SettledBet:
    profit = settle_decimal(selection=selection, odds=odds, outcome=outcome)
    return SettledBet(
        match_id=match_id,
        selection=selection,
        odds=odds,
        edge=0.05,
        ev=0.10,
        kickoff_at=kickoff,
        outcome=outcome,
        league="Premier League",
        profit=profit,
        strategy="ai_picks_value",
    )


def test_settle_decimal_win_and_loss() -> None:
    assert settle_decimal(selection="HOME", odds=2.0, outcome="HOME") == pytest.approx(1.0)
    assert settle_decimal(selection="DRAW", odds=3.5, outcome="HOME") == pytest.approx(-1.0)
    with pytest.raises(ValueError):
        settle_decimal(selection="HOME", odds=1.0, outcome="HOME")


def test_strategy_metrics_warn_on_small_n_and_compute_drawdown() -> None:
    start = datetime(2026, 8, 16, 14, tzinfo=UTC)
    bets = [
        _bet("m1", "HOME", 2.0, "HOME", start),
        _bet("m2", "AWAY", 3.0, "HOME", start),
        _bet("m3", "DRAW", 4.0, "DRAW", start),
    ]
    metrics = strategy_metrics(bets)
    assert metrics["n"] == 3
    assert metrics["n"] < INSUFFICIENT_SAMPLE_N
    assert metrics["sample_warning"] == SAMPLE_WARNING
    assert metrics["hits"] == 2
    assert metrics["hit_rate"] == pytest.approx(2 / 3)
    assert metrics["theoretical_profit"] == pytest.approx(1.0 - 1.0 + 3.0)
    assert metrics["max_drawdown_units"] >= 0
    empty = strategy_metrics([])
    assert empty["n"] == 0
    assert empty["theoretical_roi"] is None
    assert empty["sample_warning"] == SAMPLE_WARNING
