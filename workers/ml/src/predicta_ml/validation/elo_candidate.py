from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from predicta_ml.backtesting.metrics import (
    class_ece,
    class_reliability_table,
    classification_metrics,
    core_metrics,
    grouped_metrics,
)
from predicta_ml.backtesting.splits import TemporalSplitPlan, build_temporal_split_plan
from predicta_ml.calibration.methods import SigmoidCalibrator
from predicta_ml.constants import (
    CANDIDATE_MODEL_VERSION,
    CANDIDATE_STATUS,
    CLASS_INDEX,
    COLLAPSE_LOG_LOSS_MARGIN,
    COMPETITION_ORDER,
    DATASET_VERSION,
    ELO_HA_GRID,
    ELO_HOME_ADVANTAGE,
    ELO_INITIAL,
    ELO_K,
    ELO_K_GRID,
    ELO_SCALE,
    ELO_UPDATE_DELAY_HOURS,
    FEATURE_SCHEMA_VERSION,
    RANDOM_SEED,
    default_committed_reports_dir,
    default_output_dir,
)
from predicta_ml.features.dataset import FootballDataset, load_football_dataset
from predicta_ml.features.schema import ELO_FEATURES
from predicta_ml.models.elo import EloBaseline
from predicta_ml.models.elo_walk import reconstruct_pre_match_elo
from predicta_ml.models.frequency import FrequencyBaseline
from predicta_ml.registry.artifact import RegistryCard, load_registry, write_registry
from predicta_ml.robustness.checks import resolve_code_version, run_robustness_checks, seed_everything


def run_elo_validation(dataset: FootballDataset) -> dict[str, Any]:
    seed_everything(RANDOM_SEED)
    plan = build_temporal_split_plan(dataset)
    robustness = run_robustness_checks(dataset, plan)
    reconstruction_check = _reconstruction_agreement(dataset)
    sensitivity = _sensitivity_grid(dataset, plan)
    candidate_wf = _candidate_walk_forward(dataset, plan)
    draw = _draw_analysis(dataset, plan, candidate_wf)
    segments = _segment_performance(dataset, plan, candidate_wf)
    calibration = _calibration_comparison(dataset, plan)
    stability = _stability(candidate_wf, segments)
    return {
        "status": CANDIDATE_STATUS,
        "promoted_to_production": False,
        "model_version": CANDIDATE_MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "dataset_sha256": dataset.sha256,
        "random_seed": RANDOM_SEED,
        "code_version": resolve_code_version(),
        "splits": plan.to_dict(),
        "robustness": robustness,
        "candidate_parameters": {
            "k": ELO_K,
            "home_advantage": ELO_HOME_ADVANTAGE,
            "initial": ELO_INITIAL,
            "scale": ELO_SCALE,
            "update_delay_hours": ELO_UPDATE_DELAY_HOURS,
            "features": list(ELO_FEATURES),
            "source": "frozen dataset 0.3 elo_diff; K/HA sensitivity uses a causal reconstruction",
        },
        "reconstruction_check": reconstruction_check,
        "sensitivity": sensitivity,
        "walk_forward": candidate_wf["summary"],
        "draw": draw,
        "segments": segments,
        "calibration": calibration,
        "stability": stability,
        "test": calibration["test"],
    }


def _reconstruction_agreement(dataset: FootballDataset) -> dict[str, Any]:
    rebuilt = reconstruct_pre_match_elo(dataset.frame, k=ELO_K, home_advantage=ELO_HOME_ADVANTAGE)
    dataset_diff = dataset.frame["elo_diff"].to_numpy(dtype=np.float64)
    rebuilt_diff = rebuilt["reconstructed_elo_diff"].to_numpy(dtype=np.float64)
    abs_error = np.abs(dataset_diff - rebuilt_diff)
    return {
        "k": ELO_K,
        "home_advantage": ELO_HOME_ADVANTAGE,
        "mae": float(abs_error.mean()),
        "p95_abs_error": float(np.quantile(abs_error, 0.95)),
        "max_abs_error": float(abs_error.max()),
        "note": (
            "Reconstruction uses event_at + 3h because available_at is not in the parquet. "
            "The candidate keeps dataset elo_diff; reconstruction is only for the K/HA grid."
        ),
    }


def _sensitivity_grid(dataset: FootballDataset, plan: TemporalSplitPlan) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for k in ELO_K_GRID:
        for home_advantage in ELO_HA_GRID:
            rebuilt = reconstruct_pre_match_elo(dataset.frame, k=float(k), home_advantage=float(home_advantage))
            diffs = rebuilt["reconstructed_elo_diff"]
            fold_metrics: list[dict[str, Any]] = []
            for fold in plan.folds:
                model = EloBaseline(home_advantage=float(home_advantage))
                model.fit_diffs(diffs.loc[fold.train.index].to_numpy(), dataset.labels(fold.train.index))
                proba = model.predict_diffs(diffs.loc[fold.validation.index].to_numpy())
                scored: dict[str, Any] = dict(core_metrics(dataset.labels(fold.validation.index), proba))
                scored["fold"] = fold.name
                fold_metrics.append(scored)
            rows.append(
                {
                    "k": k,
                    "home_advantage": home_advantage,
                    "is_candidate_params": k == int(ELO_K) and home_advantage == int(ELO_HOME_ADVANTAGE),
                    "mean_log_loss": float(np.mean([item["log_loss"] for item in fold_metrics])),
                    "mean_brier_score": float(np.mean([item["brier_score"] for item in fold_metrics])),
                    "mean_accuracy": float(np.mean([item["accuracy"] for item in fold_metrics])),
                    "mean_ece": float(np.mean([item["ece"] for item in fold_metrics])),
                    "folds": fold_metrics,
                }
            )
    ranking = sorted(rows, key=lambda item: (float(item["mean_log_loss"]), float(item["mean_brier_score"])))
    candidate = next(item for item in rows if item["is_candidate_params"])
    losses = [float(item["mean_log_loss"]) for item in rows]
    return {
        "protocol": (
            "Causal Elo reconstruction on dataset 1X2 labels. Draw transform fit on each "
            "train fold only. Grid is a robustness probe, not a hyperparameter search: "
            "the candidate stays K=20 HA=80 regardless of the lowest grid cell."
        ),
        "n_configurations": len(rows),
        "log_loss_min": float(min(losses)),
        "log_loss_max": float(max(losses)),
        "log_loss_range": float(max(losses) - min(losses)),
        "candidate": {
            "k": candidate["k"],
            "home_advantage": candidate["home_advantage"],
            "mean_log_loss": candidate["mean_log_loss"],
            "mean_brier_score": candidate["mean_brier_score"],
            "mean_accuracy": candidate["mean_accuracy"],
            "mean_ece": candidate["mean_ece"],
            "rank_by_log_loss": 1 + next(i for i, item in enumerate(ranking) if item["is_candidate_params"]),
        },
        "best_grid_cell_not_promoted": {
            "k": ranking[0]["k"],
            "home_advantage": ranking[0]["home_advantage"],
            "mean_log_loss": ranking[0]["mean_log_loss"],
            "reason": "Grid minimum is reported for robustness only; it does not replace the candidate.",
        },
        "configurations": rows,
    }


def _candidate_walk_forward(dataset: FootballDataset, plan: TemporalSplitPlan) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    y_parts: list[np.ndarray] = []
    p_parts: list[np.ndarray] = []
    idx_parts: list[pd.Index] = []
    frequency_parts: list[np.ndarray] = []
    for fold in plan.folds:
        elo = EloBaseline()
        elo.fit(dataset, fold.train.index)
        proba = elo.predict_clipped(dataset, fold.validation.index)
        frequency = FrequencyBaseline()
        frequency.fit(dataset, fold.train.index)
        freq_proba = frequency.predict_clipped(dataset, fold.validation.index)
        y = dataset.labels(fold.validation.index)
        metrics = classification_metrics(y, proba)
        folds.append(
            {
                "fold": fold.name,
                "train": fold.train.to_dict(),
                "validation": fold.validation.to_dict(),
                "log_loss": metrics["log_loss"],
                "brier_score": metrics["brier_score"],
                "accuracy": metrics["accuracy"],
                "ece": metrics["ece"],
                "n": metrics["n"],
                "frequency_log_loss": core_metrics(y, freq_proba)["log_loss"],
                "draw_argmax_rate": float(np.mean(proba.argmax(axis=1) == CLASS_INDEX["DRAW"])),
                "hyperparameters": elo.hyperparameters(),
            }
        )
        y_parts.append(y)
        p_parts.append(proba)
        idx_parts.append(fold.validation.index)
        frequency_parts.append(freq_proba)
    y_all = np.concatenate(y_parts)
    p_all = np.vstack(p_parts)
    freq_all = np.vstack(frequency_parts)
    index = idx_parts[0]
    for extra in idx_parts[1:]:
        index = index.append(extra)
    return {
        "summary": {
            "folds": folds,
            "mean_log_loss": float(np.mean([item["log_loss"] for item in folds])),
            "mean_brier_score": float(np.mean([item["brier_score"] for item in folds])),
            "mean_accuracy": float(np.mean([item["accuracy"] for item in folds])),
            "mean_ece": float(np.mean([item["ece"] for item in folds])),
            "pooled_validation": core_metrics(y_all, p_all),
        },
        "y": y_all,
        "proba": p_all,
        "frequency_proba": freq_all,
        "index": index,
    }


def _draw_analysis(dataset: FootballDataset, plan: TemporalSplitPlan, candidate_wf: dict[str, Any]) -> dict[str, Any]:
    elo = EloBaseline()
    elo.fit(dataset, plan.final_train.index)
    windows = {
        "walk_forward_validation": (candidate_wf["y"], candidate_wf["proba"]),
        "test_raw": (
            dataset.labels(plan.test.index),
            elo.predict_clipped(dataset, plan.test.index),
        ),
    }
    report: dict[str, Any] = {"windows": {}, "why_never_argmax": None}
    for name, (y, proba) in windows.items():
        predicted = proba.argmax(axis=1)
        draw_p = proba[:, CLASS_INDEX["DRAW"]]
        home_p = proba[:, CLASS_INDEX["HOME"]]
        away_p = proba[:, CLASS_INDEX["AWAY"]]
        report["windows"][name] = {
            "n": int(y.size),
            "p_home": _distribution(home_p),
            "p_draw": _distribution(draw_p),
            "p_away": _distribution(away_p),
            "draw_argmax_count": int((predicted == CLASS_INDEX["DRAW"]).sum()),
            "draw_argmax_rate": float(np.mean(predicted == CLASS_INDEX["DRAW"])),
            "min_p_draw": float(draw_p.min()),
            "max_p_draw": float(draw_p.max()),
            "rows_where_draw_exceeds_home": int((draw_p > home_p).sum()),
            "rows_where_draw_exceeds_away": int((draw_p > away_p).sum()),
            "rows_where_draw_is_max": int((draw_p >= np.maximum(home_p, away_p)).sum()),
            "draw_class_ece": class_ece(y, proba, CLASS_INDEX["DRAW"]),
            "draw_reliability": class_reliability_table(y, proba, CLASS_INDEX["DRAW"]),
            "draw_never_removed": bool(np.all(draw_p > 0.0) and proba.shape[1] == 3),
            "actual_draw_rate": float(np.mean(y == CLASS_INDEX["DRAW"])),
            "mean_p_draw_when_draw": (
                float(draw_p[y == CLASS_INDEX["DRAW"]].mean()) if np.any(y == CLASS_INDEX["DRAW"]) else 0.0
            ),
        }
    home_at_zero = 1.0 / (1.0 + 10 ** (-(ELO_HOME_ADVANTAGE) / ELO_SCALE))
    draw_at_zero = float(elo.draw_base_)
    p_home_at_zero = (1.0 - draw_at_zero) * home_at_zero
    report["why_never_argmax"] = {
        "mechanism": (
            "P(Draw) is always emitted. Argmax never selects Draw because at elo_diff=0 "
            "home advantage +80 already makes P(Home) > P(Draw), and P(Draw) shrinks as "
            "|elo_diff| grows."
        ),
        "elo_diff_zero_expected_home_score": float(home_at_zero),
        "fitted_draw_base": float(elo.draw_base_),
        "fitted_draw_decay": float(elo.draw_decay_),
        "approx_p_home_at_elo_diff_zero": float(p_home_at_zero),
        "approx_p_draw_at_elo_diff_zero": draw_at_zero,
        "argmax_threshold": "Draw wins argmax only if P(Draw) > P(Home) and P(Draw) > P(Away).",
        "p_draw_preserved": True,
    }
    return report


def _segment_performance(
    dataset: FootballDataset,
    plan: TemporalSplitPlan,
    candidate_wf: dict[str, Any],
) -> dict[str, Any]:
    frame = dataset.frame
    wf_index = candidate_wf["index"]
    y_wf = candidate_wf["y"]
    p_wf = candidate_wf["proba"]
    freq_wf = candidate_wf["frequency_proba"]
    elo = EloBaseline()
    elo.fit(dataset, plan.final_train.index)
    y_test = dataset.labels(plan.test.index)
    p_test = elo.predict_clipped(dataset, plan.test.index)
    freq = FrequencyBaseline()
    freq.fit(dataset, plan.final_train.index)
    freq_test = freq.predict_clipped(dataset, plan.test.index)
    return {
        "walk_forward_validation": {
            "by_competition": _ordered_groups(frame, wf_index, y_wf, p_wf, "competition_id"),
            "by_season": grouped_metrics(frame, wf_index, y_wf, p_wf, "season"),
            "frequency_by_competition": _ordered_groups(frame, wf_index, y_wf, freq_wf, "competition_id"),
        },
        "test_raw": {
            "by_competition": _ordered_groups(frame, plan.test.index, y_test, p_test, "competition_id"),
            "by_season": grouped_metrics(frame, plan.test.index, y_test, p_test, "season"),
            "frequency_by_competition": _ordered_groups(frame, plan.test.index, y_test, freq_test, "competition_id"),
        },
    }


def _calibration_comparison(dataset: FootballDataset, plan: TemporalSplitPlan) -> dict[str, Any]:
    elo = EloBaseline()
    elo.fit(dataset, plan.final_train.index)
    y_fit = dataset.labels(plan.calibration_fit.index)
    y_select = dataset.labels(plan.calibration_select.index)
    y_test = dataset.labels(plan.test.index)
    raw_fit = elo.predict_clipped(dataset, plan.calibration_fit.index)
    raw_select = elo.predict_clipped(dataset, plan.calibration_select.index)
    raw_test = elo.predict_clipped(dataset, plan.test.index)
    sigmoid_select_model = SigmoidCalibrator()
    sigmoid_select_model.fit(raw_fit, y_fit)
    sigmoid_on_select = sigmoid_select_model.transform(raw_select)
    calib_index = plan.calibration_fit.index.append(plan.calibration_select.index)
    y_calib = dataset.labels(calib_index)
    raw_calib = elo.predict_clipped(dataset, calib_index)
    sigmoid_test_model = SigmoidCalibrator()
    sigmoid_test_model.fit(raw_calib, y_calib)
    sigmoid_on_test = sigmoid_test_model.transform(raw_test)
    select_raw = core_metrics(y_select, raw_select)
    select_sig = core_metrics(y_select, sigmoid_on_select)
    test_raw = classification_metrics(y_test, raw_test)
    test_sig = classification_metrics(y_test, sigmoid_on_test)
    test_raw_core = core_metrics(y_test, raw_test)
    test_sig_core = core_metrics(y_test, sigmoid_on_test)
    sigmoid_helps_select = float(select_sig["log_loss"]) < float(select_raw["log_loss"])
    sigmoid_helps_test = float(test_sig_core["log_loss"]) < float(test_raw_core["log_loss"])
    chosen = "sigmoid" if sigmoid_helps_select else "raw"
    return {
        "selection_rule": (
            "Calibration method is chosen on calibration_select after fitting on calibration_fit. "
            "Test is reported for both methods and does not change the candidate."
        ),
        "chosen_on_calibration_select": chosen,
        "sigmoid_improves_calibration_select_log_loss": sigmoid_helps_select,
        "sigmoid_improves_test_log_loss": sigmoid_helps_test,
        "calibration_select": {"raw": select_raw, "sigmoid": select_sig},
        "test": {
            "raw": test_raw_core,
            "sigmoid": test_sig_core,
            "raw_full": test_raw,
            "sigmoid_full": test_sig,
            "by_competition_raw": grouped_metrics(dataset.frame, plan.test.index, y_test, raw_test, "competition_id"),
            "by_competition_sigmoid": grouped_metrics(
                dataset.frame, plan.test.index, y_test, sigmoid_on_test, "competition_id"
            ),
            "by_season_raw": grouped_metrics(dataset.frame, plan.test.index, y_test, raw_test, "season"),
            "by_season_sigmoid": grouped_metrics(dataset.frame, plan.test.index, y_test, sigmoid_on_test, "season"),
        },
        "predictor": elo,
        "calibrator": sigmoid_test_model if chosen == "sigmoid" else None,
        "raw_test_proba": raw_test,
        "sigmoid_test_proba": sigmoid_on_test,
    }


def _stability(candidate_wf: dict[str, Any], segments: dict[str, Any]) -> dict[str, Any]:
    folds = candidate_wf["summary"]["folds"]
    log_losses = [float(item["log_loss"]) for item in folds]
    collapse: list[dict[str, Any]] = []
    by_comp = segments["walk_forward_validation"]["by_competition"]
    freq_comp = segments["walk_forward_validation"]["frequency_by_competition"]
    for competition in COMPETITION_ORDER:
        if competition not in by_comp or competition not in freq_comp:
            continue
        elo_ll = float(by_comp[competition]["log_loss"])
        freq_ll = float(freq_comp[competition]["log_loss"])
        if elo_ll > freq_ll + COLLAPSE_LOG_LOSS_MARGIN:
            collapse.append(
                {
                    "scope": "walk_forward_validation",
                    "competition": competition,
                    "elo_log_loss": elo_ll,
                    "frequency_log_loss": freq_ll,
                    "n": by_comp[competition]["n"],
                }
            )
    worst_fold = max(folds, key=lambda item: float(item["log_loss"]))
    return {
        "fold_log_loss_min": float(min(log_losses)),
        "fold_log_loss_max": float(max(log_losses)),
        "fold_log_loss_spread": float(max(log_losses) - min(log_losses)),
        "worst_fold": worst_fold["fold"],
        "collapse_vs_frequency": collapse,
        "collapse_rule": (
            f"Flag if Elo log-loss exceeds the frequency baseline by more than "
            f"{COLLAPSE_LOG_LOSS_MARGIN} on walk-forward validation."
        ),
    }


def _ordered_groups(
    frame: pd.DataFrame,
    index: pd.Index,
    y_true: np.ndarray,
    proba: np.ndarray,
    column: str,
) -> dict[str, dict[str, Any]]:
    grouped = grouped_metrics(frame, index, y_true, proba, column)
    ordered: dict[str, dict[str, Any]] = {}
    for key in COMPETITION_ORDER:
        if key in grouped:
            ordered[key] = grouped[key]
    for key, value in grouped.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def _distribution(values: np.ndarray) -> dict[str, float]:
    return {
        "min": float(np.min(values)),
        "p10": float(np.quantile(values, 0.10)),
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
    }


def candidate_registry_payload(
    dataset: FootballDataset,
    plan: TemporalSplitPlan,
    report: dict[str, Any],
) -> tuple[dict[str, Any], RegistryCard, str]:
    calibration = report["calibration"]
    chosen = calibration["chosen_on_calibration_select"]
    predictor: EloBaseline = calibration["predictor"]
    calibrator = calibration["calibrator"]
    test_block = calibration["test"][chosen]
    card = RegistryCard(
        model_version=CANDIDATE_MODEL_VERSION,
        dataset_version=dataset.dataset_version,
        feature_schema_version=dataset.feature_schema_version,
        training_period=plan.final_train.to_dict(),
        validation_period={
            "walk_forward_folds": [fold.to_dict() for fold in plan.folds],
            "calibration_fit": plan.calibration_fit.to_dict(),
            "calibration_select": plan.calibration_select.to_dict(),
        },
        test_period=plan.test.to_dict(),
        features=list(ELO_FEATURES),
        hyperparameters={
            **predictor.hyperparameters(),
            "k": ELO_K,
            "initial": ELO_INITIAL,
            "status": CANDIDATE_STATUS,
        },
        metrics={
            "walk_forward": report["walk_forward"],
            "calibration_select": report["calibration"]["calibration_select"],
            "test_raw": report["calibration"]["test"]["raw"],
            "test_sigmoid": report["calibration"]["test"]["sigmoid"],
            "test_chosen": test_block,
            "sensitivity_candidate": report["sensitivity"]["candidate"],
            "stability": {
                "fold_log_loss_spread": report["stability"]["fold_log_loss_spread"],
                "collapse_vs_frequency": report["stability"]["collapse_vs_frequency"],
            },
        },
        calibration_method=chosen,
        random_seed=RANDOM_SEED,
        code_version=str(report["code_version"]),
        dataset_sha256=dataset.sha256,
        selected_model="elo",
        ensemble_used=False,
        status=CANDIDATE_STATUS,
        notes=[
            "status=candidate; not production; not champion.",
            "No backend publish, no live predictions, no odds, no value/EV.",
            "K/HA grid was a robustness probe and did not retune the candidate.",
            "P(Draw) is always produced; argmax Draw can still be zero.",
        ],
    )
    artefact = {
        "status": CANDIDATE_STATUS,
        "selected": "elo",
        "predictors": {"elo": predictor},
        "calibrators": {"elo": calibrator} if calibrator is not None else {"elo": None},
        "feature_names": {"elo": list(ELO_FEATURES)},
        "random_seed": RANDOM_SEED,
        "dataset_sha256": dataset.sha256,
        "parameters": {
            "k": ELO_K,
            "home_advantage": ELO_HOME_ADVANTAGE,
            "scale": ELO_SCALE,
            "initial": ELO_INITIAL,
            "draw_base": predictor.draw_base_,
            "draw_decay": predictor.draw_decay_,
            "calibration_method": chosen,
        },
    }
    return artefact, card, chosen


def persist_elo_validation(dataset_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    dataset = load_football_dataset(dataset_path)
    plan = build_temporal_split_plan(dataset)
    report = run_elo_validation(dataset)
    artefact, card, chosen = candidate_registry_payload(dataset, plan, report)
    directory = output_dir or default_output_dir()
    paths = write_registry(directory / "registry", card=card, artefact=artefact)
    reloaded = load_registry(Path(paths["artefact"]))
    predictor: EloBaseline = reloaded["predictors"]["elo"]
    raw = predictor.predict_clipped(dataset, plan.test.index)
    calibrator = reloaded["calibrators"]["elo"]
    replay = raw if calibrator is None else calibrator.transform(raw)
    if chosen == "sigmoid":
        expected = report["calibration"]["sigmoid_test_proba"]
    else:
        expected = report["calibration"]["raw_test_proba"]
    if not np.allclose(replay, expected, atol=1e-12):
        raise RuntimeError("Reloaded football-elo-v1-candidate does not reproduce test probabilities.")
    public = _public_report(report, paths)
    report_path = directory / "reports" / f"{CANDIDATE_MODEL_VERSION}.validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(public, indent=2, sort_keys=True, default=_json_default), encoding="utf-8")
    committed = _write_committed_reports(card, public)
    public["report_path"] = str(report_path)
    public["registry"] = paths
    public["committed_reports"] = committed
    public["reload_matches"] = True
    return public


def _write_committed_reports(card: RegistryCard, public: dict[str, Any]) -> dict[str, str]:
    directory = default_committed_reports_dir()
    directory.mkdir(parents=True, exist_ok=True)
    registry_path = directory / f"{CANDIDATE_MODEL_VERSION}.registry.json"
    summary_path = directory / f"{CANDIDATE_MODEL_VERSION}.summary.json"
    registry_path.write_text(
        json.dumps(card.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(_committed_summary(card, public), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {"registry": str(registry_path), "summary": str(summary_path)}


def _committed_summary(card: RegistryCard, public: dict[str, Any]) -> dict[str, Any]:
    calibration = public["calibration"]
    draw_windows = public["draw"]["windows"]
    test_metrics = calibration["test"]
    return {
        "model_version": card.model_version,
        "status": card.status,
        "promoted_to_production": False,
        "dataset_version": card.dataset_version,
        "feature_schema_version": card.feature_schema_version,
        "dataset_sha256": card.dataset_sha256,
        "code_version": card.code_version,
        "random_seed": card.random_seed,
        "selected_model": card.selected_model,
        "calibration_method": card.calibration_method,
        "parameters": card.hyperparameters,
        "training_period": card.training_period,
        "validation_period": card.validation_period,
        "final_test_period": card.test_period,
        "metrics": {
            "walk_forward_mean": {
                "log_loss": public["walk_forward"]["mean_log_loss"],
                "brier_score": public["walk_forward"]["mean_brier_score"],
                "accuracy": public["walk_forward"]["mean_accuracy"],
                "ece": public["walk_forward"]["mean_ece"],
            },
            "walk_forward_folds": [
                {
                    "fold": item["fold"],
                    "n": item["n"],
                    "log_loss": item["log_loss"],
                    "brier_score": item["brier_score"],
                    "accuracy": item["accuracy"],
                    "ece": item["ece"],
                    "frequency_log_loss": item["frequency_log_loss"],
                }
                for item in public["walk_forward"]["folds"]
            ],
            "test_raw": test_metrics["raw"],
            "test_sigmoid": test_metrics["sigmoid"],
            "test_chosen": test_metrics[card.calibration_method],
        },
        "sensitivity": {
            "candidate": public["sensitivity"]["candidate"],
            "log_loss_min": public["sensitivity"]["log_loss_min"],
            "log_loss_max": public["sensitivity"]["log_loss_max"],
            "log_loss_range": public["sensitivity"]["log_loss_range"],
            "best_grid_cell_not_promoted": public["sensitivity"]["best_grid_cell_not_promoted"],
        },
        "draw": {
            "p_draw_never_removed": all(window["draw_never_removed"] for window in draw_windows.values()),
            "argmax_draw_count": {
                name: window["draw_argmax_count"] for name, window in draw_windows.items()
            },
            "why_never_argmax": public["draw"]["why_never_argmax"],
        },
        "calibration": {
            "chosen_on_calibration_select": calibration["chosen_on_calibration_select"],
            "sigmoid_improves_test_log_loss": calibration["sigmoid_improves_test_log_loss"],
            "calibration_select": calibration["calibration_select"],
        },
        "stability": public["stability"],
        "segments": public["segments"],
        "reconstruction_mae": public["reconstruction_check"]["mae"],
    }


def _public_report(report: dict[str, Any], paths: dict[str, str]) -> dict[str, Any]:
    calibration = {
        key: value
        for key, value in report["calibration"].items()
        if key not in {"predictor", "calibrator", "raw_test_proba", "sigmoid_test_proba"}
    }
    payload = dict(report)
    payload["calibration"] = calibration
    payload["registry"] = paths
    return payload


def _json_default(value: object) -> object:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
