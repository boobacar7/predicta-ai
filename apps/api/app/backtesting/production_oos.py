from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.odds.service import OddsService
from app.odds.types import Football1x2Selection, OddsSnapshot
from app.predictions.runtime import ensure_ml_on_path
from app.value_engine import calculator

ensure_ml_on_path()
from predicta_ml.oos.odds import OddsQuote, select_pit_snapshot  # noqa: E402
from predicta_ml.oos.protocol import OOS_START, VALUE_ENGINE_VERSION  # noqa: E402
from predicta_ml.oos.value import ValueCalculator  # noqa: E402


class ProductionValueCalculator:
    """Adapter over value-engine-0.1. Does not reimplement formulas."""

    version = VALUE_ENGINE_VERSION

    def implied_probability(self, odds: Decimal) -> Decimal:
        return calculator.implied_probability(odds)

    def no_vig_probabilities(self, odds_by_selection: dict[str, Decimal]) -> tuple[dict[str, Decimal], Decimal]:
        mapped = {Football1x2Selection(name): value for name, value in odds_by_selection.items()}
        simplex, overround = calculator.no_vig_probabilities(mapped)
        return {selection.value: probability for selection, probability in simplex.items()}, overround

    def edge(self, model_probability: Decimal, implied: Decimal) -> Decimal:
        return calculator.edge(model_probability, implied)

    def expected_value(self, model_probability: Decimal, odds: Decimal) -> Decimal:
        return calculator.expected_value(model_probability, odds)


def quote_from_snapshot(snapshot: OddsSnapshot) -> OddsQuote:
    odds = {item.selection.value: float(item.decimal_odds) for item in snapshot.selections}
    return OddsQuote(
        snapshot_id=snapshot.id,
        match_id=snapshot.match_id,
        provider=snapshot.source,
        bookmaker=snapshot.bookmaker,
        market=snapshot.market,
        available_at=snapshot.available_at,
        collected_at=snapshot.collected_at,
        home_odds=float(odds["HOME"]),
        draw_odds=float(odds["DRAW"]),
        away_odds=float(odds["AWAY"]),
        data_mode=str(snapshot.data_mode),
    )


def assert_odds_service_matches_protocol(
    service: OddsService,
    quotes: tuple[OddsQuote, ...],
    *,
    match_id: str,
    cutoff_at: datetime,
    kickoff_at: datetime,
) -> OddsQuote:
    selected = select_pit_snapshot(quotes, match_id=match_id, cutoff_at=cutoff_at, kickoff_at=kickoff_at)
    snapshot = service.market_at(match_id=match_id, market="1X2", cutoff_at=cutoff_at)
    if snapshot.id != selected.snapshot_id:
        raise AssertionError("OddsService selected a different snapshot than the frozen OOS odds policy.")
    return selected


def quotes_from_persisted_analytical(path: Path) -> tuple[OddsQuote, ...]:
    """Rebuild PIT quotes from a previously scored analytical dataset. Zero API credits."""

    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("analytical_dataset")
    if not isinstance(rows, list):
        return ()
    unique: dict[str, OddsQuote] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("temporal_split")) != "final_test":
            continue
        kickoff = datetime.fromisoformat(str(raw["kickoff_at"]).replace("Z", "+00:00"))
        if kickoff < OOS_START:
            continue
        snapshot_id = str(raw.get("snapshot_at") or "") + "::" + str(raw["match_id"])
        available = raw.get("available_at")
        if available is None or raw.get("odds_home") is None:
            continue
        unique[str(raw["match_id"])] = OddsQuote(
            snapshot_id=snapshot_id,
            match_id=str(raw["match_id"]),
            provider=str(raw.get("provider") or "the-odds-api-v4"),
            bookmaker=str(raw.get("bookmaker") or "unknown"),
            market="1X2",
            available_at=datetime.fromisoformat(str(available).replace("Z", "+00:00")),
            collected_at=datetime.fromisoformat(str(available).replace("Z", "+00:00")),
            home_odds=float(raw["odds_home"]),
            draw_odds=float(raw["odds_draw"]),
            away_odds=float(raw["odds_away"]),
            data_mode=str(raw.get("data_mode") or "live"),
        )
    return tuple(unique.values())


def production_calculator() -> ValueCalculator:
    return ProductionValueCalculator()


def persisted_score_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "workers"
        / "ingestion"
        / "var"
        / "persisted-final-test-history-score.json"
    )


def optional_persisted_oos_quotes() -> tuple[OddsQuote, ...]:
    path = persisted_score_path()
    if not path.is_file():
        return ()
    return quotes_from_persisted_analytical(path)


def report_without_rows(report: dict[str, Any]) -> dict[str, Any]:
    payload = dict(report)
    payload["row_count"] = len(report.get("rows") or [])
    payload.pop("rows", None)
    return payload
