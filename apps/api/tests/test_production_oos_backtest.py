from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.ai_picks.config import AI_PICKS_VERSION
from app.backtesting.production_oos import ProductionValueCalculator, quote_from_snapshot
from app.odds.providers import LiveOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.value_engine.calculator import VALUE_ENGINE_VERSION, edge, expected_value, implied_probability
from predicta_ml.oos.ai_picks import decide_picks
from predicta_ml.oos.errors import OosProtocolError
from predicta_ml.oos.odds import select_pit_snapshot
from predicta_ml.oos.predictions import FrozenPrediction
from predicta_ml.oos.protocol import OOS_START
from predicta_ml.oos.provenance import assert_window_is_oos, audit_model_provenance
from predicta_ml.oos.value import evaluate_match_value


def _snapshot(
    *,
    snapshot_id: str,
    match_id: str,
    available_at: datetime,
    home: str,
    draw: str,
    away: str,
) -> OddsSnapshot:
    return OddsSnapshot(
        id=snapshot_id,
        provider_id=snapshot_id,
        match_id=match_id,
        bookmaker="book-a",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal(home)),
            OddsSelection(Football1x2Selection.DRAW, Decimal(draw)),
            OddsSelection(Football1x2Selection.AWAY, Decimal(away)),
        ),
        collected_at=available_at,
        available_at=available_at,
        source="the-odds-api-v4",
        data_mode="live",
        raw_payload_id="raw-1",
    )


def test_production_value_engine_parity() -> None:
    calculator = ProductionValueCalculator()
    odds = Decimal("2.50")
    assert calculator.implied_probability(odds) == implied_probability(odds)
    assert calculator.expected_value(Decimal("0.45"), odds) == expected_value(Decimal("0.45"), odds)
    implied = implied_probability(odds)
    assert calculator.edge(Decimal("0.45"), implied) == edge(Decimal("0.45"), implied)
    prediction = FrozenPrediction("m1", 0.45, 0.25, 0.30, "football-elo-v1-candidate", "raw", False)
    kickoff = datetime(2026, 8, 22, 15, tzinfo=UTC)
    snapshot = _snapshot(
        snapshot_id="s1",
        match_id="m1",
        available_at=kickoff - timedelta(hours=1),
        home="2.50",
        draw="3.50",
        away="2.80",
    )
    quote = quote_from_snapshot(snapshot)
    value = evaluate_match_value(prediction, quote, calculator)
    home = next(item for item in value.selections if item.selection == "HOME")
    assert value.value_engine_version == VALUE_ENGINE_VERSION
    assert abs(home.implied_probability - float(implied_probability(Decimal("2.50")))) < 1e-12
    assert abs(home.ev - float(expected_value(Decimal("0.45"), Decimal("2.50")))) < 1e-12


def test_odds_service_matches_oos_policy() -> None:
    kickoff = datetime(2026, 8, 22, 15, tzinfo=UTC)
    pit = _snapshot(
        snapshot_id="pit",
        match_id="m1",
        available_at=kickoff - timedelta(hours=2),
        home="2.10",
        draw="3.40",
        away="3.60",
    )
    later = _snapshot(
        snapshot_id="later",
        match_id="m1",
        available_at=kickoff - timedelta(minutes=20),
        home="2.05",
        draw="3.50",
        away="3.70",
    )
    future = _snapshot(
        snapshot_id="future",
        match_id="m1",
        available_at=kickoff + timedelta(minutes=5),
        home="1.50",
        draw="4.00",
        away="6.00",
    )
    quotes = (quote_from_snapshot(pit), quote_from_snapshot(later), quote_from_snapshot(future))
    selected = select_pit_snapshot(quotes, match_id="m1", cutoff_at=kickoff, kickoff_at=kickoff)
    service = OddsService(
        provider=LiveOddsProvider(enable_live=True, snapshots=(pit, later, future)),
        repository=InMemoryOddsRepository(),
    )
    snapshot = service.market_at(match_id="m1", market="1X2", cutoff_at=kickoff)
    assert snapshot.id == selected.snapshot_id == "later"


def test_ai_picks_eligibility_matches_published_thresholds() -> None:
    calculator = ProductionValueCalculator()
    prediction = FrozenPrediction("m1", 0.48, 0.24, 0.28, "football-elo-v1-candidate", "raw", False)
    kickoff = datetime(2026, 8, 22, 15, tzinfo=UTC)
    snapshot = _snapshot(
        snapshot_id="s1",
        match_id="m1",
        available_at=kickoff - timedelta(hours=1),
        home="2.20",
        draw="3.40",
        away="3.50",
    )
    quote = quote_from_snapshot(snapshot)
    value = evaluate_match_value(prediction, quote, calculator)
    decisions = decide_picks(prediction=prediction, quote=quote, value=value, cutoff_at=kickoff)
    eligible = {item.selection for item in decisions if item.eligible}
    excluded = {item.selection: item.exclusion_reason for item in decisions if not item.eligible}
    assert AI_PICKS_VERSION == "ai-picks-0.1"
    assert eligible
    allowed = {"negative_ev", "negative_edge", "stale_odds"}
    assert all(reason in allowed or reason is None for reason in excluded.values())


def test_invalid_oos_window_rejected_by_protocol() -> None:
    provenance = audit_model_provenance()
    try:
        assert_window_is_oos(
            start=datetime(2024, 8, 16, tzinfo=UTC),
            end_exclusive=datetime(2024, 10, 1, tzinfo=UTC),
            provenance=provenance,
        )
    except OosProtocolError as exc:
        assert "before the artefact freeze" in str(exc)
    else:
        raise AssertionError("2024 window must not be accepted as OOS")
    assert_window_is_oos(
        start=OOS_START,
        end_exclusive=datetime(2026, 9, 10, tzinfo=UTC),
        provenance=provenance,
    )
