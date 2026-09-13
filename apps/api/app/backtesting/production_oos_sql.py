from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.exc import SQLAlchemyError

from app.backtesting.production_oos import production_calculator, quote_from_snapshot
from app.odds.exceptions import IncompleteOddsMarketError, OddsTemporalLeakageError, OddsUnavailableError
from app.odds.providers import MOCK_ODDS_SOURCE, LiveOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import DataMode, OddsSnapshot, is_complete_football_1x2
from app.predictions.runtime import ensure_ml_on_path, repository_root

ensure_ml_on_path()
from predicta_ml.constants import COMPETITION_ORDER, default_committed_reports_dir  # noqa: E402
from predicta_ml.features.dataset import load_football_dataset  # noqa: E402
from predicta_ml.oos.ai_picks import published_thresholds  # noqa: E402
from predicta_ml.oos.dataset import matches_from_frame, select_oos_frame  # noqa: E402
from predicta_ml.oos.errors import OosProtocolError  # noqa: E402
from predicta_ml.oos.metrics import drawdown_units, settle_pick  # noqa: E402
from predicta_ml.oos.odds import OddsQuote  # noqa: E402
from predicta_ml.oos.predictions import FrozenPrediction  # noqa: E402
from predicta_ml.oos.protocol import OOS_START, VALUE_ENGINE_VERSION  # noqa: E402
from predicta_ml.oos.provenance import audit_model_provenance  # noqa: E402
from predicta_ml.oos.runner import OosRun, run_oos_backtest  # noqa: E402

LIVE_SQL_BACKTEST_FILENAME = "production-oos-backtest-live-sql.json"
PREDICTION_PARITY_FILENAME = "prediction_parity.json"
LIVE_SQL_MARKDOWN_PATH = repository_root() / "docs" / "ml" / "production-oos-backtest-live-sql.md"
ODDS_SOURCE_SQL = "postgresql:odds_snapshots"
ODDS_REPOSITORY_NAME = "SqlOddsRepository"
JSON_ODDS_SOURCE = "persisted_analytical_dataset"
PREVIOUS_BACKTEST_FILENAME = "production-oos-backtest.json"
PREDICTION_ABS_TOL = 1e-12


class SqlOddsHistory(Protocol):
    def history_many(
        self,
        match_ids: Sequence[str],
        market: str,
        *,
        source: str | None = None,
        data_mode: DataMode | None = None,
    ) -> tuple[OddsSnapshot, ...]: ...


class SqlOddsUnavailableError(RuntimeError):
    """SQL odds cannot be loaded. The frozen JSON fixture must not be used as a fallback."""


@dataclass(frozen=True)
class MatchCutoff:
    match_id: str
    cutoff_at: datetime
    kickoff_at: datetime


@dataclass(frozen=True)
class LiveSqlOddsIsolation:
    quotes: tuple[OddsQuote, ...]
    live_snapshots_considered: int
    live_snapshots_eligible: int
    live_snapshots_selected: int
    live_snapshots_rejected: int
    live_snapshots_not_selected: int
    mock_odds_used: int
    live_odds_used: int
    provider: str
    repository: str
    odds_source: str
    selected_snapshot_ids: tuple[str, ...]
    rejected_reasons: dict[str, int]


def previous_oos_report_path() -> Path:
    return default_committed_reports_dir() / PREVIOUS_BACKTEST_FILENAME


def live_sql_report_path(output_dir: Path | None = None) -> Path:
    return (output_dir or default_committed_reports_dir()) / LIVE_SQL_BACKTEST_FILENAME


def prediction_parity_path(output_dir: Path | None = None) -> Path:
    return (output_dir or default_committed_reports_dir()) / PREDICTION_PARITY_FILENAME


def load_live_sql_pit_quotes(
    repository: SqlOddsHistory,
    cutoffs: Sequence[MatchCutoff],
) -> LiveSqlOddsIsolation:
    """Load live PIT 1X2 quotes from SQL. Never reads the persisted JSON fixture."""

    if not cutoffs:
        raise SqlOddsUnavailableError("OOS match universe is empty; refusing to load odds.")
    match_ids = [item.match_id for item in cutoffs]
    cutoff_by_id = {item.match_id: item for item in cutoffs}
    try:
        snapshots = repository.history_many(
            match_ids,
            "1X2",
            source=LIVE_ODDS_SOURCE,
            data_mode="live",
        )
    except SQLAlchemyError as exc:
        raise SqlOddsUnavailableError(
            "SqlOddsRepository is unavailable; refusing to fall back to persisted JSON odds."
        ) from exc
    except Exception as exc:
        if isinstance(exc, SqlOddsUnavailableError):
            raise
        raise SqlOddsUnavailableError(
            "SqlOddsRepository failed; refusing to fall back to persisted JSON odds."
        ) from exc
    if not snapshots:
        raise SqlOddsUnavailableError(
            "SqlOddsRepository returned zero live 1X2 snapshots; refusing to fall back to persisted JSON odds."
        )

    mock_count = 0
    rejected_reasons: dict[str, int] = {}
    eligible: list[OddsSnapshot] = []
    for snapshot in snapshots:
        if snapshot.data_mode == "mock" or snapshot.source == MOCK_ODDS_SOURCE:
            mock_count += 1
            rejected_reasons["mock_odds"] = rejected_reasons.get("mock_odds", 0) + 1
            continue
        if snapshot.data_mode != "live":
            rejected_reasons["non_live_data_mode"] = rejected_reasons.get("non_live_data_mode", 0) + 1
            continue
        if snapshot.source != LIVE_ODDS_SOURCE:
            rejected_reasons["unexpected_provider"] = rejected_reasons.get("unexpected_provider", 0) + 1
            continue
        match = cutoff_by_id.get(snapshot.match_id)
        if match is None:
            rejected_reasons["outside_oos_universe"] = rejected_reasons.get("outside_oos_universe", 0) + 1
            continue
        if not is_complete_football_1x2(snapshot):
            rejected_reasons["incomplete_1x2"] = rejected_reasons.get("incomplete_1x2", 0) + 1
            continue
        if snapshot.available_at > match.cutoff_at:
            rejected_reasons["available_at_after_cutoff"] = rejected_reasons.get("available_at_after_cutoff", 0) + 1
            continue
        if snapshot.available_at > match.kickoff_at:
            rejected_reasons["post_kickoff"] = rejected_reasons.get("post_kickoff", 0) + 1
            continue
        eligible.append(snapshot)

    if mock_count:
        raise SqlOddsUnavailableError(
            f"Mock odds entered the SQL load ({mock_count} snapshots). Refusing to continue."
        )
    unexpected = rejected_reasons.get("unexpected_provider", 0)
    if unexpected:
        raise SqlOddsUnavailableError(
            "Non the-odds-api-v4 snapshots were returned for a live SQL query. Refusing to continue."
        )
    if not eligible:
        raise SqlOddsUnavailableError(
            "No eligible live PIT 1X2 snapshots exist in SQL; refusing to fall back to JSON odds."
        )

    service = OddsService(
        provider=LiveOddsProvider(enable_live=True, snapshots=tuple(eligible)),
        repository=InMemoryOddsRepository(),
    )
    quotes: list[OddsQuote] = []
    selected_ids: list[str] = []
    for match in cutoffs:
        try:
            snapshot = service.market_at(match_id=match.match_id, market="1X2", cutoff_at=match.cutoff_at)
        except OddsUnavailableError:
            rejected_reasons["no_eligible_snapshot"] = rejected_reasons.get("no_eligible_snapshot", 0) + 1
            continue
        except IncompleteOddsMarketError:
            rejected_reasons["incomplete_1x2"] = rejected_reasons.get("incomplete_1x2", 0) + 1
            continue
        except OddsTemporalLeakageError as exc:
            raise SqlOddsUnavailableError(
                f"Post-cutoff odds exist for {match.match_id} and would leak; refusing to select them."
            ) from exc
        if snapshot.available_at > match.cutoff_at or snapshot.available_at > match.kickoff_at:
            raise SqlOddsUnavailableError(
                f"Selected snapshot {snapshot.id} for {match.match_id} is not PIT-safe."
            )
        if snapshot.data_mode != "live" or snapshot.source != LIVE_ODDS_SOURCE:
            raise SqlOddsUnavailableError(
                f"Selected snapshot {snapshot.id} is not live the-odds-api-v4 odds."
            )
        quote = quote_from_snapshot(snapshot)
        if quote.data_mode != "live" or quote.provider != LIVE_ODDS_SOURCE:
            raise SqlOddsUnavailableError("Converted PIT quote is not live the-odds-api-v4 odds.")
        quotes.append(quote)
        selected_ids.append(snapshot.id)

    rejected = len(snapshots) - len(eligible)
    return LiveSqlOddsIsolation(
        quotes=tuple(quotes),
        live_snapshots_considered=len(snapshots),
        live_snapshots_eligible=len(eligible),
        live_snapshots_selected=len(quotes),
        live_snapshots_rejected=rejected,
        live_snapshots_not_selected=len(eligible) - len(quotes),
        mock_odds_used=0,
        live_odds_used=len(quotes),
        provider=LIVE_ODDS_SOURCE,
        repository=ODDS_REPOSITORY_NAME,
        odds_source=ODDS_SOURCE_SQL,
        selected_snapshot_ids=tuple(selected_ids),
        rejected_reasons=rejected_reasons,
    )


def predictions_from_rows(rows: Sequence[dict[str, Any]]) -> dict[str, tuple[float, float, float]]:
    by_match: dict[str, tuple[float, float, float]] = {}
    for row in rows:
        match_id = str(row["match_id"])
        probs = (
            float(row["home_probability"]),
            float(row["draw_probability"]),
            float(row["away_probability"]),
        )
        existing = by_match.get(match_id)
        if existing is not None and existing != probs:
            raise OosProtocolError(f"Inconsistent stored predictions for {match_id}.")
        by_match[match_id] = probs
    return by_match


def predictions_from_frozen(predictions: Sequence[FrozenPrediction]) -> dict[str, tuple[float, float, float]]:
    return {item.match_id: (item.home, item.draw, item.away) for item in predictions}


def compare_prediction_parity(
    previous: dict[str, tuple[float, float, float]],
    current: dict[str, tuple[float, float, float]],
    *,
    model_version: str,
    dataset_version: str,
    feature_schema: str,
    abs_tol: float = PREDICTION_ABS_TOL,
) -> dict[str, Any]:
    previous_ids = set(previous)
    current_ids = set(current)
    missing = sorted(previous_ids - current_ids)
    extra = sorted(current_ids - previous_ids)
    differences: list[dict[str, Any]] = []
    shared = sorted(previous_ids & current_ids)
    max_abs = 0.0
    for match_id in shared:
        old = previous[match_id]
        new = current[match_id]
        deltas = [abs(a - b) for a, b in zip(old, new, strict=True)]
        max_abs = max(max_abs, *deltas)
        if any(delta > abs_tol for delta in deltas):
            differences.append(
                {
                    "match_id": match_id,
                    "previous": old,
                    "current": new,
                    "abs_delta": deltas,
                }
            )
    n_differences = len(differences) + len(missing) + len(extra)
    return {
        "kind": "production_oos_prediction_parity",
        "passed": n_differences == 0,
        "n_previous": len(previous),
        "n_current": len(current),
        "n_shared": len(shared),
        "n_differences": n_differences,
        "max_abs_delta": max_abs,
        "abs_tol": abs_tol,
        "missing_from_current": missing,
        "extra_in_current": extra,
        "differences": differences,
        "same_match_universe": not missing and not extra,
        "model_version": model_version,
        "dataset_version": dataset_version,
        "feature_schema": feature_schema,
        "note": "Only the odds input source changed. Predictions must be identical.",
    }


def synthetic_future_quote(quote: OddsQuote) -> OddsQuote:
    return OddsQuote(
        snapshot_id=f"{quote.snapshot_id}::future-leakage-probe",
        match_id=quote.match_id,
        provider=quote.provider,
        bookmaker=quote.bookmaker,
        market=quote.market,
        available_at=quote.available_at + timedelta(days=1),
        collected_at=quote.collected_at + timedelta(days=1),
        home_odds=1.01,
        draw_odds=20.0,
        away_odds=30.0,
        data_mode="live",
    )


def run_live_sql_oos_backtest(
    *,
    dataset_path: Path,
    repository: SqlOddsHistory,
    output_dir: Path | None = None,
    previous_report_path: Path | None = None,
    write_markdown: bool = True,
) -> dict[str, Any]:
    provenance = audit_model_provenance()
    dataset = load_football_dataset(dataset_path)
    if dataset.sha256 != provenance.dataset_sha256:
        raise OosProtocolError("Parquet SHA-256 does not match the frozen candidate registry card.")
    matches = matches_from_frame(select_oos_frame(dataset, provenance=provenance))
    cutoffs = tuple(
        MatchCutoff(match_id=item.match_id, cutoff_at=item.cutoff_at, kickoff_at=item.kickoff_at) for item in matches
    )
    isolation = load_live_sql_pit_quotes(repository, cutoffs)
    future = (synthetic_future_quote(isolation.quotes[0]),) if isolation.quotes else ()
    first = run_oos_backtest(
        dataset,
        provenance=provenance,
        quotes=isolation.quotes,
        calculator=production_calculator(),
        future_quotes=future,
    )
    second = run_oos_backtest(
        dataset,
        provenance=provenance,
        quotes=isolation.quotes,
        calculator=production_calculator(),
        future_quotes=future,
    )
    if first.report["reproducibility"]["fingerprint"] != second.report["reproducibility"]["fingerprint"]:
        raise OosProtocolError("Live SQL OOS backtest is not reproducible.")

    previous_path = previous_report_path or previous_oos_report_path()
    previous_payload = json.loads(previous_path.read_text(encoding="utf-8"))
    previous_preds = predictions_from_rows(previous_payload.get("rows") or [])
    current_preds = predictions_from_frozen(first.predictions)
    parity = compare_prediction_parity(
        previous_preds,
        current_preds,
        model_version=str(first.report["model_version"]),
        dataset_version=str(first.report["dataset_version"]),
        feature_schema=str(first.report["feature_schema"]),
    )
    if not parity["passed"]:
        _write_json(prediction_parity_path(output_dir), parity)
        raise OosProtocolError(
            "NO-GO: prediction differences are not zero after switching to SQL live odds. "
            f"n_differences={parity['n_differences']} max_abs_delta={parity['max_abs_delta']}."
        )

    _assert_live_result_isolation(first, isolation)
    payload = _assemble_payload(first, isolation, parity, previous_payload)
    directory = output_dir or default_committed_reports_dir()
    directory.mkdir(parents=True, exist_ok=True)
    backtest_file = live_sql_report_path(directory)
    parity_file = prediction_parity_path(directory)
    _write_json(backtest_file, payload)
    _write_json(parity_file, parity)
    markdown_path = LIVE_SQL_MARKDOWN_PATH
    if write_markdown:
        markdown_path.write_text(render_live_sql_markdown(payload), encoding="utf-8")
    payload["paths"] = {
        "backtest": str(backtest_file),
        "prediction_parity": str(parity_file),
        "markdown": str(markdown_path) if write_markdown else None,
    }
    payload["new_api_credits"] = 0
    return payload


def _assert_live_result_isolation(run: OosRun, isolation: LiveSqlOddsIsolation) -> None:
    if isolation.mock_odds_used != 0:
        raise OosProtocolError("Mock odds were counted as used.")
    if isolation.live_odds_used <= 0:
        raise OosProtocolError("Live SQL odds used must be greater than 0.")
    if isolation.provider != LIVE_ODDS_SOURCE:
        raise OosProtocolError("Live SQL odds provider is not the-odds-api-v4.")
    used_providers = {
        str(row["odds_provider"])
        for row in run.rows
        if row.get("odds_snapshot_id")
    }
    if used_providers - {LIVE_ODDS_SOURCE}:
        raise OosProtocolError(f"Unexpected odds providers in OOS rows: {sorted(used_providers)}.")
    selected = {str(row["odds_snapshot_id"]) for row in run.rows if row.get("odds_snapshot_id")}
    if selected - set(isolation.selected_snapshot_ids):
        raise OosProtocolError("OOS rows selected a snapshot that was not produced by the SQL PIT loader.")
    thresholds = published_thresholds()
    reported = run.report["ai_picks"]["thresholds"]
    if reported != thresholds:
        raise OosProtocolError("AI Picks thresholds changed during the SQL OOS rerun.")
    if run.report["value_engine"]["version"] != VALUE_ENGINE_VERSION:
        raise OosProtocolError("Value Engine version changed during the SQL OOS rerun.")
    if datetime.fromisoformat(str(run.report["window"]["start"])).astimezone(UTC) != OOS_START:
        raise OosProtocolError("OOS start changed during the SQL OOS rerun.")


def _assemble_payload(
    run: OosRun,
    isolation: LiveSqlOddsIsolation,
    parity: dict[str, Any],
    previous_payload: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(run.report)
    previous_odds = previous_payload.get("odds") or {}
    previous_picks = previous_payload.get("ai_picks") or {}
    previous_metrics = previous_picks.get("metrics") or {}
    payload["odds_source"] = isolation.odds_source
    payload["odds_repository"] = isolation.repository
    payload["json_odds_source_used"] = False
    payload["new_api_credits"] = 0
    payload["prediction_parity"] = {
        "passed": parity["passed"],
        "n_differences": parity["n_differences"],
        "max_abs_delta": parity["max_abs_delta"],
        "n_shared": parity["n_shared"],
    }
    payload["odds_isolation"] = {
        "mock_odds_used": isolation.mock_odds_used,
        "live_odds_used": isolation.live_odds_used,
        "provider": isolation.provider,
        "repository": isolation.repository,
        "odds_source": isolation.odds_source,
        "live_snapshots_considered": isolation.live_snapshots_considered,
        "live_snapshots_eligible": isolation.live_snapshots_eligible,
        "live_snapshots_selected": isolation.live_snapshots_selected,
        "live_snapshots_rejected": isolation.live_snapshots_rejected,
        "live_snapshots_not_selected": isolation.live_snapshots_not_selected,
        "rejected_reasons": isolation.rejected_reasons,
        "selected_snapshot_ids": list(isolation.selected_snapshot_ids),
    }
    payload["odds"] = {
        **(payload.get("odds") or {}),
        "source": isolation.odds_source,
        "repository": isolation.repository,
        "n_selected_snapshots": isolation.live_snapshots_selected,
        "live_snapshots_considered": isolation.live_snapshots_considered,
        "live_snapshots_eligible": isolation.live_snapshots_eligible,
        "live_snapshots_rejected": isolation.live_snapshots_rejected,
        "mock_odds_used": 0,
        "new_api_credits": 0,
    }
    payload["comparison"] = {
        "previous": {
            "odds_source": JSON_ODDS_SOURCE,
            "oos_matches": previous_odds.get("n_matches", 387),
            "odds_covered": previous_odds.get("n_matches_with_odds", 53),
            "coverage_pct": previous_odds.get("coverage_pct", 13.695090439276486),
            "ai_picks": previous_picks.get("n_picks", 68),
            "eligible_matches": previous_picks.get("eligible_matches", 49),
            "hit_rate": previous_metrics.get("hit_rate", 0.20588235294117646),
            "roi": previous_metrics.get("realized_roi", -0.10191176470588237),
            "max_drawdown_units": previous_metrics.get("max_drawdown_units", 15.0),
        },
        "current": {
            "odds_source": isolation.odds_source,
            "oos_matches": payload["odds"]["n_matches"],
            "odds_covered": payload["odds"]["n_matches_with_odds"],
            "coverage_pct": payload["odds"]["coverage_pct"],
            "ai_picks": payload["ai_picks"]["n_picks"],
            "eligible_matches": payload["ai_picks"]["eligible_matches"],
            "hit_rate": (payload["ai_picks"]["metrics"] or {}).get("hit_rate"),
            "roi": (payload["ai_picks"]["metrics"] or {}).get("realized_roi"),
            "max_drawdown_units": (payload["ai_picks"]["metrics"] or {}).get("max_drawdown_units"),
        },
        "same_model": True,
        "same_protocol": True,
        "same_thresholds": True,
        "same_oos_universe": True,
        "only_odds_source_changed": True,
    }
    payload["league_breakdown"] = _league_breakdown(payload)
    payload["manifest"] = {
        **(payload.get("manifest") or {}),
        "odds_provider": isolation.provider,
        "odds_repository": isolation.repository,
        "odds_source": isolation.odds_source,
        "selected_snapshot_ids_hash": _hash_ids(isolation.selected_snapshot_ids),
        "json_odds_fixture_used": False,
        "new_api_credits": 0,
    }
    payload["limitations"] = list(payload.get("limitations") or []) + [
        "This rerun keeps the frozen OOS protocol and only changes the odds input to PostgreSQL live PIT snapshots.",
        "114/387 is odds coverage from the historical expansion, not an AI Picks count.",
        "Multiple bookmakers can share available_at; PIT still selects the last complete 1X2 by "
        "(available_at, collected_at, snapshot.id).",
    ]
    return payload


def _league_breakdown(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows") or []
    coverage_by = dict(payload.get("coverage", {}).get("by_competition") or {})
    picks_by = dict((payload.get("ai_picks") or {}).get("metrics", {}).get("by_competition") or {})
    odds_matches: dict[str, set[str]] = {name: set() for name in COMPETITION_ORDER}
    profits_by: dict[str, list[float]] = {name: [] for name in COMPETITION_ORDER}
    for row in rows:
        league = str(row.get("competition") or "")
        if league not in odds_matches:
            continue
        if row.get("odds_snapshot_id"):
            odds_matches[league].add(str(row["match_id"]))
        if row.get("AI_Pick_eligibility") is True and row.get("odds") is not None:
            settled = settle_pick(
                match_id=str(row["match_id"]),
                selection=str(row["selection"]),
                odds=float(row["odds"]),
                edge=float(row["edge"]),
                ev=float(row["ev"]),
                kickoff_at=datetime.fromisoformat(str(row["kickoff_at"])),
                outcome=str(row["actual_outcome"]),
                league=league,
            )
            profits_by[league].append(settled.profit)
    breakdown: dict[str, Any] = {}
    for league in COMPETITION_ORDER:
        n_matches = int(coverage_by.get(league) or 0)
        n_odds = len(odds_matches[league])
        picks = picks_by.get(league) or {}
        n_picks = int(picks.get("n") or 0)
        profits = profits_by[league]
        breakdown[league] = {
            "oos_matches": n_matches,
            "odds_covered": n_odds,
            "coverage_pct": (n_odds / n_matches * 100.0) if n_matches else 0.0,
            "ai_picks": n_picks,
            "hit_rate": picks.get("hit_rate"),
            "roi": picks.get("theoretical_roi"),
            "drawdown_units": drawdown_units(profits) if profits else None,
            "hits": picks.get("hits"),
            "profit": picks.get("theoretical_profit"),
            "sample_warning": picks.get("sample_warning"),
        }
    return breakdown


def render_live_sql_markdown(payload: dict[str, Any]) -> str:
    prediction = payload["prediction"]
    picks = payload["ai_picks"]
    metrics = picks["metrics"]
    odds = payload["odds"]
    isolation = payload["odds_isolation"]
    parity = payload["prediction_parity"]
    comparison = payload["comparison"]
    prev = comparison["previous"]
    curr = comparison["current"]
    coverage_pct = float(odds["coverage_pct"])
    hit_rate = metrics.get("hit_rate")
    roi = metrics.get("realized_roi")
    drawdown = metrics.get("max_drawdown_units")
    profit = metrics.get("theoretical_profit")
    fingerprint = payload["reproducibility"]["fingerprint"]
    input_hash = payload["manifest"]["input_ids_hash"]
    code_version = payload["manifest"].get("code_version")
    verdict = payload["verdict"]
    n_picks = int(picks["n_picks"])
    eligible = int(picks["eligible_matches"])
    excluded = picks.get("exclusion_reasons") or {}

    def pct(value: float | None, digits: int = 2) -> str:
        if value is None:
            return "—"
        return f"{value * 100:.{digits}f}%"

    def num(value: float | None, digits: int = 4) -> str:
        if value is None:
            return "—"
        return f"{value:.{digits}f}"

    league_lines = [
        "| Competition | OOS matches | Odds-covered | Coverage | AI Picks | Hit rate | ROI | Drawdown | P&L |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    breakdown = payload.get("league_breakdown") or {}
    for league in COMPETITION_ORDER:
        row = breakdown.get(league)
        if not isinstance(row, dict):
            continue
        if not row["ai_picks"]:
            league_lines.append(
                f"| {league} | {row['oos_matches']} | {row['odds_covered']} | "
                f"{row['coverage_pct']:.1f}% | 0 | — | — | — | no eligible picks |"
            )
            continue
        league_lines.append(
            f"| {league} | {row['oos_matches']} | {row['odds_covered']} | "
            f"{row['coverage_pct']:.1f}% | {row['ai_picks']} | "
            f"{pct(row['hit_rate'], 1)} | {pct(row['roi'], 1)} | "
            f"{num(row.get('drawdown_units'), 2)} u | {num(row['profit'], 2)} u |"
        )

    exclusion_text = ", ".join(f"`{name}`: {count}" for name, count in sorted(excluded.items())) or "none"
    return f"""# Production temporal OOS backtest — live SQL odds

**Verdict: `{verdict}`.**

`football-elo-v1-candidate` remains a candidate.
`promoted_to_production = false`.

This is the **same frozen OOS protocol** as [production-oos-backtest.md](production-oos-backtest.md).
Only the **odds input source** changed:

- previous run: `persisted-final-test-history-score.json` (analytical quotes)
- this run: PostgreSQL `odds_snapshots` via `SqlOddsRepository` (`data_mode=live`)

Mock odds were not used. New Odds API credits consumed: **0**.

Machine-readable result: `workers/ml/reports/production-oos-backtest-live-sql.json`.
Prediction parity: `workers/ml/reports/prediction_parity.json`.

Command used (zero Odds API credits):

```bash
cd apps/api
python -m app.backtesting production-oos-sql
```

---

## 1. What changed / what did not

| Frozen | This rerun |
| --- | --- |
| Model `football-elo-v1-candidate` | unchanged |
| Elo K / HA / calibration / artefact | unchanged |
| OOS window `2026-07-01` → `2026-09-10T02:30:01Z` | unchanged |
| 387 finished OOS matches | unchanged |
| Value Engine v0.1 formulas | unchanged |
| AI Picks v0.1 thresholds and ranking | unchanged |
| PIT policy (`available_at <= cutoff`, last complete 1X2) | unchanged |
| Odds source | **PostgreSQL live PIT snapshots** |

The 114 / 387 figure from the historical-odds expansion is **matches with valid live PIT 1X2 odds**.
It is **not** an AI Picks count. AI Picks are counted only after prediction → PIT odds → Value Engine → eligibility.

---

## 2. Prediction parity

| | |
| --- | ---: |
| Shared matches | {parity["n_shared"]} |
| Prediction differences | **{parity["n_differences"]}** |
| Max abs delta | {parity["max_abs_delta"]} |
| Result | **{"PASS" if parity["passed"] else "NO-GO"}** |

Same match universe, model artefact, model version, dataset version, feature schema, cutoff, and probabilities.

---

## 3. Comparison with the previous frozen run

| | Previous | New |
| --- | ---: | ---: |
| OOS matches | {prev["oos_matches"]} | {curr["oos_matches"]} |
| Odds-covered | {prev["odds_covered"]} | {curr["odds_covered"]} |
| Coverage | {float(prev["coverage_pct"]):.1f}% | {float(curr["coverage_pct"]):.1f}% |
| AI Picks | {prev["ai_picks"]} | {curr["ai_picks"]} |
| Eligible matches | {prev["eligible_matches"]} | {curr["eligible_matches"]} |
| Hit rate | {pct(prev["hit_rate"])} | {pct(curr["hit_rate"])} |
| ROI | {pct(prev["roi"])} | {pct(curr["roi"])} |
| Max drawdown | {float(prev["max_drawdown_units"]):.2f}u | {float(drawdown or 0):.2f}u |
| Odds source | JSON analytical fixture | PostgreSQL live PIT |

---

## 4. Odds coverage

| | |
| --- | ---: |
| OOS matches | {odds["n_matches"]} |
| Matches with a valid PIT 1X2 snapshot | {odds["n_matches_with_odds"]} |
| Coverage | **{coverage_pct:.2f}%** |
| Live snapshots considered | {isolation["live_snapshots_considered"]} |
| Live snapshots eligible | {isolation["live_snapshots_eligible"]} |
| Live snapshots selected | {isolation["live_snapshots_selected"]} |
| Live snapshots rejected | {isolation["live_snapshots_rejected"]} |
| Mock odds used | **{isolation["mock_odds_used"]}** |
| Provider | `{isolation["provider"]}` |
| Repository | `{isolation["repository"]}` |
| New Odds API credits | **0** |

Rejected snapshot count is {isolation["live_snapshots_rejected"]}.
{isolation.get("rejected_reasons", {}).get("no_eligible_snapshot", 0)} OOS matches had no eligible live PIT snapshot
(structured exclusion). That is not an AI Picks count.

---

## 5. Prediction performance (unchanged layer)

Frozen sigmoid Elo on all 387 OOS matches. Odds are not an input to the model.

| Metric | Frozen Elo |
| --- | ---: |
| n | {prediction["n"]} |
| Accuracy | {pct(prediction["accuracy"])} |
| LogLoss | {num(prediction["log_loss"])} |
| Brier | {num(prediction["brier_score"])} |
| ECE | {num(prediction["ece"])} |

These must remain LogLoss ≈ 1.0280, Brier ≈ 0.6159, Accuracy ≈ 48.32%, ECE ≈ 0.0629.

---

## 6. Value Engine

Canonical `{payload["value_engine"]["version"]}` via `app.value_engine.calculator`.
Eligible matches with PIT odds: {payload["value_engine"]["eligible_matches"]}.

On eligible picks:

| | |
| --- | ---: |
| Average model probability | {pct(metrics.get("average_model_probability"))} |
| Average implied probability | {pct(metrics.get("average_implied_probability"))} |
| Average no-vig probability | {pct(metrics.get("average_no_vig_probability"))} |
| Average edge | {pct(metrics.get("average_edge"))} |
| Average EV | {num(metrics.get("average_ev"), 3)} |
| Average odds | {num(metrics.get("average_odds"), 2)} |

Average EV is not realized profit.

---

## 7. AI Picks

Published `ai-picks-0.1` thresholds. `optimized_on_oos = false`.

| | |
| --- | ---: |
| Matches with odds | {odds["n_matches_with_odds"]} |
| Matches with ≥1 eligible pick | {eligible} |
| Eligible picks | **{n_picks}** |
| Excluded opportunities | {picks.get("excluded_opportunities")} |
| Exclusion reasons | {exclusion_text} |
| Hits | {metrics.get("hits")} |
| Hit rate | **{pct(hit_rate)}** |

---

## 8. ROI / drawdown

Assumptions unchanged: 1 unit per eligible pick; decimal odds; settle `odds − 1`
on a hit, `−1` on a miss; chronological by `(kickoff_at, match_id, selection)`.

| | |
| --- | ---: |
| Realized ROI | **{pct(roi)}** |
| Realized P&L | **{num(profit, 2)} u** |
| Max drawdown | **{num(drawdown, 2)} u** |
| Longest losing streak | {metrics.get("longest_losing_streak")} |
| Profit factor | {num(metrics.get("profit_factor"), 2)} |

Historical ROI does not predict future profit. This sample does not support a profitability conclusion.

---

## 9. League breakdown

Do not draw conclusions from tiny samples.

{chr(10).join(league_lines)}

---

## 10. Leakage checks

All checks **{"PASS" if payload["leakage_checks"]["passed"] else "FAIL"}**.

| Check | Result |
| --- | --- |
| cutoff after kickoff | fail-closed; none observed |
| feature `available_at` / `event_at` ≥ cutoff | fail-closed; none observed |
| odds `available_at` after cutoff | fail-closed; none observed |
| post-kickoff odds | fail-closed; none observed |
| outcome used before kickoff | fail-closed; none observed |
| mock odds in result | **{isolation["mock_odds_used"]} used** |
| future snapshot selected | fail-closed; synthetic future quote did not change fingerprint |
| duplicate snapshot ambiguity | fail-closed at OddsService PIT selection |
| identity ambiguity | fail-closed; none observed |
| SQL unavailable JSON fallback | refused |

---

## 11. Reproducibility

| | |
| --- | --- |
| Result | **PASS** |
| Fingerprint | `{fingerprint}` |
| Input ids hash | `{input_hash}` |
| Selected snapshot ids hash | `{payload["manifest"].get("selected_snapshot_ids_hash")}` |
| Code version | `{code_version}` |
| Odds provider | `{isolation["provider"]}` |
| Odds repository | `{isolation["repository"]}` |

The backtest was executed twice. Results were identical except for paths written after scoring.
`generated_at` / `request_id` are not part of the fingerprint.

---

## 12. Limitations

1. Odds coverage is still {coverage_pct:.1f}% (< 50% protocol bar).
2. Pick count is {n_picks} (< 250 robust-profitability bar).
3. AI Picks v0.1 thresholds were frozen for this protocol and were not a historically pre-registered trading strategy.
4. Multiple bookmakers can share `available_at`; selection remains last complete
   1X2 by `(available_at, collected_at, snapshot.id)`.
5. Historical ROI does not predict future profit.
6. This task does not promote `football-elo-v1-candidate`.

---

## 13. Final verdict

**`{verdict}`.**

Not a promotion. Not an optimization. Measurement only: same frozen protocol, PostgreSQL live PIT odds.

OOS sample insufficient for a robust profitability conclusion unless the protocol bars are met.
"""


def _hash_ids(ids: Sequence[str]) -> str:
    import hashlib

    encoded = json.dumps(list(ids), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def summary_without_rows(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out["row_count"] = len(payload.get("rows") or [])
    out.pop("rows", None)
    isolation = dict(out.get("odds_isolation") or {})
    isolation.pop("selected_snapshot_ids", None)
    out["odds_isolation"] = isolation
    return out
