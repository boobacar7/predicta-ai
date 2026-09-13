from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai_picks.config import AI_PICKS_VERSION
from app.backtesting.expanded import (
    AGE_BINS_HOURS,
    EDGE_BINS,
    EV_BINS,
    PROB_BINS,
    STAKE_NOTE,
    STAKE_POLICY,
    _bucket_metrics,
    _comparisons,
    _enrich_model_performance,
    _multiple_picks,
)
from app.backtesting.fixture_universe import LIVE_COMPETITIONS
from app.backtesting.persisted import (
    _evaluate_persisted,
    _verdict,
    catalog_from_parquet,
)
from app.backtesting.pilot import catalog_identity_exclusions
from app.backtesting.types import CatalogMatch
from app.core.clock import Clock
from app.odds.types import OddsSnapshot
from app.predictions.runtime import ensure_ingestion_on_path, ensure_ml_on_path
from app.predictions.service import FootballPredictionService, build_football_prediction_service
from app.predictions.types import CANDIDATE_MODEL_VERSION
from app.value_engine.calculator import VALUE_ENGINE_VERSION

ensure_ml_on_path()
ensure_ingestion_on_path()
from predicta_ingestion.final_test_history import (  # noqa: E402
    FINAL_TEST_HISTORY_KIND,
    FINAL_TEST_WINDOWS,
    FinalTestWindow,
    windows_artefact,
)
from predicta_ml.backtesting.value_metrics import max_drawdown_units  # noqa: E402
from predicta_ml.constants import DATASET_VERSION  # noqa: E402

FINAL_TEST_CLOCK = datetime(2026, 9, 7, tzinfo=UTC)
FINAL_TEST_PICKS_LIMIT = 5000

# Descriptive analysis bins only. Not selection rules. User-specified grid.
ODDS_BINS: tuple[tuple[str, float | None, float | None], ...] = (
    ("<2", None, 2.0),
    ("2-3", 2.0, 3.0),
    ("3-5", 3.0, 5.0),
    ("5-10", 5.0, 10.0),
    (">10", 10.0, None),
)

SCORING_WINDOWS: tuple[tuple[str, datetime, datetime, bool], ...] = tuple(
    (item.window_id, item.start, item.end, item.additional) for item in FINAL_TEST_WINDOWS
)


def final_test_catalog_from_parquet(
    dataset_path: Path,
    *,
    names: dict[str, tuple[str, str]] | None = None,
    windows: tuple[FinalTestWindow, ...] = FINAL_TEST_WINDOWS,
) -> tuple[CatalogMatch, ...]:
    catalog: list[CatalogMatch] = []
    seen: set[str] = set()
    for window in windows:
        for match in catalog_from_parquet(
            dataset_path,
            window_start=window.start,
            window_end=window.end,
            names=names,
        ):
            if match.match_id in seen:
                continue
            if match.league not in LIVE_COMPETITIONS:
                continue
            seen.add(match.match_id)
            catalog.append(match)
    return tuple(sorted(catalog, key=lambda item: (item.kickoff_at, item.match_id)))


def run_persisted_final_test_history(
    *,
    catalog: tuple[CatalogMatch, ...],
    snapshots: tuple[OddsSnapshot, ...],
    predictions: FootballPredictionService | None = None,
    dataset_path: Path | None = None,
    registry_dir: Path | None = None,
    persist_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score predeclared PL + Ligue 1 final-test windows independently. Does not tune thresholds."""

    clock = Clock(FINAL_TEST_CLOCK)
    predictor = predictions
    if predictor is None:
        if dataset_path is None or registry_dir is None:
            raise ValueError("Final-test scoring needs a predictor or parquet + registry.")
        predictor = build_football_prediction_service(
            clock=clock,
            registry_dir=registry_dir,
            dataset_path=dataset_path,
            model_version=CANDIDATE_MODEL_VERSION,
        )
    exclusions = catalog_identity_exclusions(catalog)
    snapshots_by_match: dict[str, list[OddsSnapshot]] = {}
    for snapshot in snapshots:
        snapshots_by_match.setdefault(snapshot.match_id, []).append(snapshot)

    window_reports: list[dict[str, Any]] = []
    for window in FINAL_TEST_WINDOWS:
        window_catalog = tuple(
            item for item in catalog if window.start <= item.kickoff_at < window.end
        )
        if not window_catalog:
            continue
        window_ids = {item.match_id for item in window_catalog}
        window_snapshots = tuple(
            snapshot
            for match_id in window_ids
            for snapshot in snapshots_by_match.get(match_id, ())
        )
        first = _evaluate_persisted(
            window_catalog,
            window_snapshots,
            predictor,
            clock,
            identity_exclusions=exclusions,
            picks_limit=FINAL_TEST_PICKS_LIMIT,
            kind=FINAL_TEST_HISTORY_KIND,
        )
        second = _evaluate_persisted(
            window_catalog,
            window_snapshots,
            predictor,
            clock,
            identity_exclusions=exclusions,
            picks_limit=FINAL_TEST_PICKS_LIMIT,
            kind=FINAL_TEST_HISTORY_KIND,
        )
        first["reproducibility"] = {
            "passed": first["fingerprint"] == second["fingerprint"],
            "first": first["fingerprint"],
            "second": second["fingerprint"],
        }
        first["window"] = window.to_dict()
        first["temporal_split"] = window.elo_temporal_split
        first["model_performance"] = _enrich_model_performance(first, window_catalog, exclusions, predictor)
        first["multiple_picks"] = _multiple_picks(first, window_catalog, exclusions)
        first["descriptive_slices"] = _window_slices(first)
        first["analytical_dataset"] = _analytical_dataset(first, window_catalog, exclusions, window)
        first["comparisons"] = _comparisons(first)
        first["pnl"] = _pnl(first)
        first["verdict"] = _verdict(first)
        window_reports.append(first)

    additional = [item for item in window_reports if item["window"]["additional"]]
    existing = [item for item in window_reports if not item["window"]["additional"]]
    ensemble = _ensemble_from_windows(additional, catalog, exclusions, predictor, snapshots)
    existing_block = existing[0] if existing else None
    combined_repro = all(item["reproducibility"]["passed"] for item in window_reports)
    combined_pit = all(item["pit"]["passed"] for item in window_reports)
    combined_value = all(item["value_parity"]["passed"] for item in window_reports)
    combined_picks = all(item["ai_picks_parity"]["passed"] for item in window_reports)
    summary = {
        "kind": FINAL_TEST_HISTORY_KIND,
        "model_version": CANDIDATE_MODEL_VERSION,
        "model_status": "candidate",
        "value_engine_version": VALUE_ENGINE_VERSION,
        "ai_picks_version": AI_PICKS_VERSION,
        "dataset_version": DATASET_VERSION,
        "candidate_promoted": False,
        "thresholds": {
            "minimum_edge": 0.0,
            "minimum_ev": 0.0,
            "minimum_model_probability": 0.0,
            "maximum_odds_age_seconds": 24 * 3600,
            "optimized_on_test": False,
        },
        "stake_policy": STAKE_POLICY,
        "stake_note": STAKE_NOTE,
        "windows_artefact": windows_artefact(),
        "persist": persist_meta or {},
        "window_reports": [
            {
                "window_id": item["window"]["window_id"],
                "name": item["window"]["name"],
                "additional": item["window"]["additional"],
                "temporal_split": item["temporal_split"],
                "start": item["window"]["start"],
                "end": item["window"]["end"],
                "dataset": item["dataset"],
                "model_performance": item["model_performance"],
                "value_performance": item["value_performance"],
                "ai_picks_performance": item["ai_picks_performance"],
                "multiple_picks": item["multiple_picks"],
                "descriptive_slices": item["descriptive_slices"],
                "pnl": item["pnl"],
                "pit": item["pit"],
                "value_parity": item["value_parity"],
                "ai_picks_parity": item["ai_picks_parity"],
                "reproducibility": {"passed": item["reproducibility"]["passed"]},
            }
            for item in window_reports
        ],
        "additional_ensemble": ensemble,
        "existing_official_final_test": None
        if existing_block is None
        else {
            "window_id": existing_block["window"]["window_id"],
            "dataset": existing_block["dataset"],
            "model_performance": existing_block["model_performance"],
            "value_performance": existing_block["value_performance"],
            "ai_picks_performance": existing_block["ai_picks_performance"],
            "multiple_picks": existing_block["multiple_picks"],
            "descriptive_slices": existing_block["descriptive_slices"],
            "pnl": existing_block["pnl"],
        },
        "analytical_dataset": [row for item in window_reports for row in item["analytical_dataset"]],
        "pit": {"passed": combined_pit, "rule": window_reports[0]["pit"]["rule"] if window_reports else ""},
        "value_parity": {"passed": combined_value},
        "ai_picks_parity": {"passed": combined_picks, "version": AI_PICKS_VERSION},
        "reproducibility": {"passed": combined_repro},
        "source": "the-odds-api-v4",
    }
    summary["verdict"] = _dataset_verdict(summary, window_reports)
    return summary


def _window_slices(report: dict[str, Any]) -> dict[str, Any]:
    picks = _pick_rows(report)
    return {
        "purpose": "Descriptive only. Do not select the best bucket retroactively.",
        "competition": report["ai_picks_performance"].get("by_competition", {}),
        "selection": report["ai_picks_performance"].get("by_selection", {}),
        "odds": _bucket_metrics(picks, lambda row: float(row["odds"]), ODDS_BINS),
        "edge": _bucket_metrics(picks, lambda row: float(row["edge"]), EDGE_BINS),
        "ev": _bucket_metrics(picks, lambda row: float(row["ev"]), EV_BINS),
        "model_probability": _bucket_metrics(picks, lambda row: float(row["model_probability"]), PROB_BINS),
        "odds_age_hours": _bucket_metrics(picks, lambda row: float(row["odds_age_hours"]), AGE_BINS_HOURS),
    }


def _pick_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    by_match = {item["match_id"]: item for item in report["rows"]}
    rows: list[dict[str, Any]] = []
    for match_id, selection, rank in report["fingerprint"]["picks"]:
        match = by_match[match_id]
        key = selection.lower()
        if key == "home":
            probability = match["home_probability"]
        elif key == "away":
            probability = match["away_probability"]
        else:
            probability = match["draw_probability"]
        age_seconds = match["odds_age_seconds"] or 0.0
        rows.append(
            {
                "match_id": match_id,
                "selection": selection,
                "rank": rank,
                "odds": match[f"{key}_odds"],
                "edge": match[f"{key}_edge"],
                "ev": match[f"{key}_ev"],
                "model_probability": probability,
                "odds_age_hours": float(age_seconds) / 3600.0,
                "outcome": match["outcome"],
                "league": match["league"],
                "kickoff_at": match["kickoff_at"],
                "hit": selection == match["outcome"],
            }
        )
    return rows


def _pnl(report: dict[str, Any]) -> dict[str, Any]:
    picks = sorted(_pick_rows(report), key=lambda row: (str(row["kickoff_at"]), row["match_id"], row["selection"]))
    profits: list[float] = []
    curve: list[dict[str, Any]] = []
    equity = 0.0
    for row in picks:
        profit = (float(row["odds"]) - 1.0) if row["hit"] else -1.0
        equity += profit
        profits.append(profit)
        curve.append(
            {
                "match_id": row["match_id"],
                "selection": row["selection"],
                "kickoff_at": row["kickoff_at"],
                "profit": profit,
                "equity": equity,
            }
        )
    drawdown = max_drawdown_units(profits) if profits else 0.0
    return {
        "n": len(picks),
        "theoretical_profit": float(sum(profits)) if profits else 0.0,
        "max_drawdown_units": drawdown,
        "max_drawdown_pct_of_stake": None if not picks else drawdown / len(picks),
        "curve": curve,
        "note": "Chronological by (kickoff_at, match_id, selection). 1 unit per pick. No look-ahead.",
    }


def _analytical_dataset(
    report: dict[str, Any],
    catalog: tuple[CatalogMatch, ...],
    exclusions: dict[str, str],
    window: FinalTestWindow,
) -> list[dict[str, Any]]:
    by_id = {item.match_id: item for item in catalog}
    pick_index = {(item[0], item[1]): item[2] for item in report["fingerprint"]["picks"]}
    exclusion_by_key = {
        (item["match_id"], item.get("selection")): item.get("reason")
        for item in report.get("ai_picks_exclusions", [])
    }
    dataset: list[dict[str, Any]] = []
    for row in report["rows"]:
        match = by_id[row["match_id"]]
        argmax = _argmax_from_row(row)
        identity_reason = exclusions.get(match.match_id) or row.get("identity_exclusion")
        for selection in ("HOME", "DRAW", "AWAY"):
            key = selection.lower()
            eligible = (match.match_id, selection) in pick_index
            dataset.append(
                {
                    "match_id": match.match_id,
                    "competition": match.league,
                    "kickoff_at": match.kickoff_at.isoformat(),
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "result": match.outcome,
                    "model_probability_home": row["home_probability"],
                    "model_probability_draw": row["draw_probability"],
                    "model_probability_away": row["away_probability"],
                    "model_favorite": argmax,
                    "odds_home": row["home_odds"],
                    "odds_draw": row["draw_odds"],
                    "odds_away": row["away_odds"],
                    "provider": report["source"],
                    "bookmaker": row["bookmaker"],
                    "snapshot_at": row["available_at"],
                    "available_at": row["available_at"],
                    "odds_age": row["odds_age_seconds"],
                    "implied_probability": row[f"{key}_implied"],
                    "no_vig_probability": row[f"{key}_no_vig"],
                    "edge": row[f"{key}_edge"],
                    "EV": row[f"{key}_ev"],
                    "AI_Pick_selection": selection if eligible else None,
                    "AI_Pick_rank": pick_index.get((match.match_id, selection)),
                    "AI_Pick_eligibility": eligible,
                    "exclusion_reason": identity_reason
                    or exclusion_by_key.get((match.match_id, selection))
                    or (None if eligible else exclusion_by_key.get((match.match_id, None))),
                    "model_version": CANDIDATE_MODEL_VERSION,
                    "dataset_version": DATASET_VERSION,
                    "value_engine_version": VALUE_ENGINE_VERSION,
                    "ai_picks_version": AI_PICKS_VERSION,
                    "cutoff_at": match.kickoff_at.isoformat(),
                    "data_mode": "live",
                    "window_id": window.window_id,
                    "temporal_split": window.elo_temporal_split,
                }
            )
    return dataset


def _argmax_from_row(row: dict[str, Any]) -> str | None:
    probs = {
        "HOME": row["home_probability"],
        "DRAW": row["draw_probability"],
        "AWAY": row["away_probability"],
    }
    if any(value is None for value in probs.values()):
        return None
    return max(probs, key=lambda name: (probs[name], name))


def _ensemble_from_windows(
    window_reports: list[dict[str, Any]],
    catalog: tuple[CatalogMatch, ...],
    exclusions: dict[str, str],
    predictions: FootballPredictionService,
    snapshots: tuple[OddsSnapshot, ...],
) -> dict[str, Any]:
    """Descriptive concatenation of independently scored additional windows. Not a global rerank."""

    del snapshots
    additional_ids = {
        item.match_id
        for window in FINAL_TEST_WINDOWS
        if window.additional
        for item in catalog
        if window.start <= item.kickoff_at < window.end
    }
    subset = tuple(item for item in catalog if item.match_id in additional_ids)
    if not window_reports:
        return {"n_windows": 0, "note": "No additional windows scored."}
    picks: list[dict[str, Any]] = []
    for report in window_reports:
        picks.extend(_pick_rows(report))
    picks = sorted(picks, key=lambda row: (str(row["kickoff_at"]), row["match_id"], row["selection"]))
    n = len(picks)
    hits = sum(1 for item in picks if item["hit"])
    profit = 0.0
    profits: list[float] = []
    for item in picks:
        value = (float(item["odds"]) - 1.0) if item["hit"] else -1.0
        profit += value
        profits.append(value)
    drawdown = max_drawdown_units(profits) if profits else 0.0
    matches_scored = sum(int(item["dataset"]["identity_matched"]) for item in window_reports)
    table = []
    for report in window_reports:
        picks_n = report["ai_picks_performance"]["n"]
        table.append(
            {
                "window_id": report["window"]["window_id"],
                "matches": report["dataset"]["identity_matched"],
                "picks": picks_n,
                "hit_rate": report["ai_picks_performance"]["hit_rate"],
                "theoretical_roi": report["ai_picks_performance"]["theoretical_roi"],
                "max_drawdown_units": report["ai_picks_performance"]["max_drawdown_units"],
                "max_drawdown_pct_of_stake": report["ai_picks_performance"]["max_drawdown_pct_of_stake"],
            }
        )
    model = None
    if subset:
        dummy = {
            "model_performance": {},
            "fingerprint": {"picks": []},
            "ai_picks_performance": {"n": 0},
        }
        model = _enrich_model_performance(dummy, subset, exclusions, predictions)
    return {
        "note": (
            "Descriptive ensemble of independently scored additional windows. "
            "Eligibility is per match; ranks are within-window. "
            "Not Elo OOS — additional windows have temporal_split=final_train. "
            "Insufficient to conclude future profitability."
        ),
        "n_windows": len(window_reports),
        "matches": matches_scored,
        "picks": n,
        "hits": hits,
        "hit_rate": None if n == 0 else hits / n,
        "theoretical_profit": profit,
        "theoretical_roi": None if n == 0 else profit / n,
        "max_drawdown_units": drawdown,
        "max_drawdown_pct_of_stake": None if n == 0 else drawdown / n,
        "table": table,
        "model_performance": model,
        "by_selection": _group_picks(picks, "selection"),
        "by_competition": _group_picks(picks, "league"),
        "odds": _bucket_metrics(picks, lambda row: float(row["odds"]), ODDS_BINS),
        "edge": _bucket_metrics(picks, lambda row: float(row["edge"]), EDGE_BINS),
        "ev": _bucket_metrics(picks, lambda row: float(row["ev"]), EV_BINS),
        "multiple_picks": _ensemble_multiple_picks(window_reports),
    }


def _group_picks(picks: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in picks:
        grouped.setdefault(str(item[key]), []).append(item)
    report: dict[str, dict[str, Any]] = {}
    for name, items in sorted(grouped.items()):
        n = len(items)
        hits = sum(1 for item in items if item["hit"])
        profit = sum((float(item["odds"]) - 1.0) if item["hit"] else -1.0 for item in items)
        report[name] = {
            "n": n,
            "hits": hits,
            "hit_rate": None if n == 0 else hits / n,
            "theoretical_roi": None if n == 0 else profit / n,
            "theoretical_profit": profit,
            "note": "descriptive_only",
        }
    return report


def _ensemble_multiple_picks(window_reports: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    picks = 0
    eligible = 0
    for report in window_reports:
        block = report["multiple_picks"]
        counts["matches_with_0"] += int(block.get("matches_with_0", 0))
        counts["matches_with_1"] += int(block.get("matches_with_1", 0))
        counts["matches_with_2"] += int(block.get("matches_with_2", 0))
        counts["matches_with_3"] += int(block.get("matches_with_3", 0))
        picks += int(block.get("picks", 0))
        eligible += int(block.get("eligible_matches", 0))
    return {
        **counts,
        "eligible_matches": eligible,
        "picks": picks,
        "stake_policy": STAKE_POLICY,
        "note": STAKE_NOTE,
    }


def _dataset_verdict(summary: dict[str, Any], window_reports: list[dict[str, Any]]) -> str:
    if (
        not summary["pit"]["passed"]
        or not summary["value_parity"]["passed"]
        or not summary["reproducibility"]["passed"]
        or not summary["ai_picks_parity"]["passed"]
    ):
        return "NO-GO"
    additional_matches = summary["additional_ensemble"].get("matches") or 0
    if additional_matches < 250:
        return "GO WITH CONDITIONS"
    missing_odds = any(
        item["dataset"]["matches_with_odds"] < item["dataset"]["identity_matched"] for item in window_reports
    )
    if missing_odds:
        return "GO WITH CONDITIONS"
    return "GO WITH CONDITIONS"
