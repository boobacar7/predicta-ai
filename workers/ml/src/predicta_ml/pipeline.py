from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from predicta_ml.backtesting.metrics import classification_metrics, grouped_metrics, reliability_table
from predicta_ml.backtesting.splits import TemporalSplitPlan, TemporalWindow, build_temporal_split_plan
from predicta_ml.calibration.methods import ProbabilityCalibrator, isotonic_is_eligible, make_calibrator
from predicta_ml.constants import MODEL_VERSION, RANDOM_SEED, default_output_dir
from predicta_ml.ensemble.average import ProbabilityEnsemble, inverse_log_loss_weights, should_keep_ensemble
from predicta_ml.features.audit import audit_dataset
from predicta_ml.features.dataset import FootballDataset, load_football_dataset
from predicta_ml.features.schema import BOOSTING_FEATURES, ELO_FEATURES, POISSON_FEATURES
from predicta_ml.models.boosting import LightGBMPredictor, XGBoostPredictor
from predicta_ml.models.elo import EloBaseline
from predicta_ml.models.frequency import FrequencyBaseline
from predicta_ml.models.poisson import PoissonBaseline
from predicta_ml.registry.artifact import RegistryCard, load_registry, write_registry
from predicta_ml.robustness.checks import run_robustness_checks, seed_everything

PredictorFactory = Callable[[], Any]

MODEL_FACTORIES: dict[str, PredictorFactory] = {
    "frequency": FrequencyBaseline,
    "elo": EloBaseline,
    "poisson": PoissonBaseline,
    "xgboost": XGBoostPredictor,
    "lightgbm": LightGBMPredictor,
}

CALIBRATION_METHODS: tuple[str, ...] = ("raw", "sigmoid", "isotonic")


def run_benchmark(dataset_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    seed_everything(RANDOM_SEED)
    dataset = load_football_dataset(dataset_path)
    audit = audit_dataset(dataset)
    plan = build_temporal_split_plan(dataset)
    robustness = run_robustness_checks(dataset, plan)
    walk_forward = _walk_forward(dataset, plan)
    fitted = _fit_final_train(dataset, plan.final_train)
    calibration = _compare_calibration(dataset, plan, fitted)
    ensemble_decision = _evaluate_ensemble(dataset, plan, fitted, calibration)
    test_report = _final_test(dataset, plan, fitted, calibration, ensemble_decision)
    selected_name = ensemble_decision["registered_name"]
    card = _registry_card(dataset, plan, walk_forward, calibration, ensemble_decision, test_report, robustness, fitted)
    registry_dir = output_dir or default_output_dir()
    artefact = {
        "selected": selected_name,
        "predictors": fitted,
        "calibrators": test_report["calibrators"],
        "ensemble": ensemble_decision["ensemble"],
        "feature_names": {
            "frequency": [],
            "elo": list(ELO_FEATURES),
            "poisson": list(POISSON_FEATURES),
            "xgboost": list(BOOSTING_FEATURES),
            "lightgbm": list(BOOSTING_FEATURES),
        },
        "random_seed": RANDOM_SEED,
        "dataset_sha256": dataset.sha256,
    }
    paths = write_registry(registry_dir / "registry", card=card, artefact=artefact)
    reloaded = load_registry(Path(paths["artefact"]))
    replay = _replay_test(dataset, plan, reloaded)
    selected_proba = np.asarray(test_report["selected_test_proba"])
    test_report["reload_matches"] = bool(np.allclose(replay, selected_proba, atol=1e-12))
    if not test_report["reload_matches"]:
        raise RuntimeError("Reloaded artefact does not reproduce test probabilities.")
    report = {
        "audit": audit,
        "splits": plan.to_dict(),
        "robustness": robustness,
        "walk_forward": walk_forward,
        "calibration": {
            "methods": calibration["metrics"],
            "selected_method_per_model": calibration["selected_method"],
            "selection_window": plan.calibration_select.to_dict(),
            "fit_window": plan.calibration_fit.to_dict(),
        },
        "ensemble": {
            "used": ensemble_decision["used"],
            "reason": ensemble_decision["reason"],
            "members": ensemble_decision["members"],
            "candidates": ensemble_decision.get("candidates", ensemble_decision["members"]),
            "weights": ensemble_decision["weights"],
            "selection_metrics": ensemble_decision["selection_metrics"],
        },
        "test": test_report["public"],
        "selected_model": selected_name,
        "registry": paths,
        "model_version": MODEL_VERSION,
        "random_seed": RANDOM_SEED,
        "code_version": robustness["code_version"],
    }
    report_path = (output_dir or default_output_dir()) / "reports" / f"{MODEL_VERSION}.benchmark.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(report_path, report)
    report["report_path"] = str(report_path)
    return report


def _walk_forward(dataset: FootballDataset, plan: TemporalSplitPlan) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, factory in MODEL_FACTORIES.items():
        folds: list[dict[str, Any]] = []
        for fold in plan.folds:
            model = factory()
            model.fit(dataset, fold.train.index)
            proba = model.predict_clipped(dataset, fold.validation.index)
            metrics = classification_metrics(dataset.labels(fold.validation.index), proba)
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
                }
            )
        summary[name] = {
            "folds": folds,
            "mean_log_loss": float(np.mean([item["log_loss"] for item in folds])),
            "mean_brier_score": float(np.mean([item["brier_score"] for item in folds])),
            "mean_accuracy": float(np.mean([item["accuracy"] for item in folds])),
            "mean_ece": float(np.mean([item["ece"] for item in folds])),
        }
    ranking = sorted(summary, key=lambda name: (summary[name]["mean_log_loss"], summary[name]["mean_brier_score"]))
    summary["_ranking"] = ranking
    return summary


def _fit_final_train(dataset: FootballDataset, window: TemporalWindow) -> dict[str, Any]:
    fitted: dict[str, Any] = {}
    for name, factory in MODEL_FACTORIES.items():
        model = factory()
        model.fit(dataset, window.index)
        fitted[name] = model
    return fitted


def _compare_calibration(
    dataset: FootballDataset,
    plan: TemporalSplitPlan,
    fitted: dict[str, Any],
) -> dict[str, Any]:
    y_fit = dataset.labels(plan.calibration_fit.index)
    y_select = dataset.labels(plan.calibration_select.index)
    metrics: dict[str, dict[str, Any]] = {}
    selected_method: dict[str, str] = {}
    calibrators: dict[str, dict[str, ProbabilityCalibrator]] = {}
    raw_fit: dict[str, np.ndarray] = {}
    raw_select: dict[str, np.ndarray] = {}
    for name, model in fitted.items():
        raw_fit[name] = model.predict_clipped(dataset, plan.calibration_fit.index)
        raw_select[name] = model.predict_clipped(dataset, plan.calibration_select.index)
        metrics[name] = {}
        calibrators[name] = {}
        eligible: dict[str, float] = {}
        for method in CALIBRATION_METHODS:
            if method == "isotonic" and not isotonic_is_eligible(y_fit):
                metrics[name][method] = {
                    "eligible": False,
                    "reason": "insufficient_calibration_fit_support",
                }
                continue
            calibrator = make_calibrator(method)
            if method != "raw":
                calibrator.fit(raw_fit[name], y_fit)
            proba = calibrator.transform(raw_select[name])
            scored = classification_metrics(y_select, proba)
            scored["eligible"] = True
            metrics[name][method] = scored
            calibrators[name][method] = calibrator
            eligible[method] = float(scored["log_loss"])
            selected_method[name] = min(eligible, key=lambda method: eligible[method])
    return {
        "metrics": metrics,
        "selected_method": selected_method,
        "calibrators": calibrators,
        "raw_fit": raw_fit,
        "raw_select": raw_select,
        "y_fit": y_fit,
        "y_select": y_select,
    }


def _evaluate_ensemble(
    dataset: FootballDataset,
    plan: TemporalSplitPlan,
    fitted: dict[str, Any],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    y_select = calibration["y_select"]
    calibrated: dict[str, np.ndarray] = {}
    for name, model in fitted.items():
        method = calibration["selected_method"][name]
        calibrator = calibration["calibrators"][name][method]
        calibrated[name] = calibrator.transform(model.predict_clipped(dataset, plan.calibration_select.index))
    ranking: list[str] = [
        name
        for name in sorted(
            fitted,
            key=lambda item: float(calibration["metrics"][item][calibration["selected_method"][item]]["log_loss"]),
        )
    ]
    best_single = ranking[0]
    best_single_ll = float(calibration["metrics"][best_single][calibration["selected_method"][best_single]]["log_loss"])
    candidates = [name for name in ranking if name in {"elo", "poisson", "xgboost", "lightgbm"}]
    if len(candidates) < 2:
        return {
            "used": False,
            "reason": "fewer_than_two_candidates",
            "registered_name": best_single,
            "members": [best_single],
            "candidates": candidates,
            "weights": [1.0],
            "ensemble": None,
            "selection_metrics": classification_metrics(y_select, calibrated[best_single]),
            "calibrated_select": calibrated,
        }
    log_losses = {
        name: float(calibration["metrics"][name][calibration["selected_method"][name]]["log_loss"])
        for name in candidates
    }
    weights = inverse_log_loss_weights(log_losses)
    ensemble = ProbabilityEnsemble(tuple(candidates), weights)
    mixed = ensemble.combine({name: calibrated[name] for name in candidates})
    ensemble_metrics = classification_metrics(y_select, mixed)
    used = should_keep_ensemble(
        ensemble_log_loss=float(ensemble_metrics["log_loss"]),
        best_single_log_loss=best_single_ll,
    )
    if used:
        return {
            "used": True,
            "reason": "ensemble_improved_calibration_select_log_loss",
            "registered_name": "ensemble",
            "members": list(candidates),
            "candidates": list(candidates),
            "weights": [float(value) for value in ensemble.weights],
            "ensemble": ensemble,
            "selection_metrics": ensemble_metrics,
            "calibrated_select": calibrated,
        }
    return {
        "used": False,
        "reason": "ensemble_did_not_improve_out_of_sample_log_loss",
        "registered_name": best_single,
        "members": [best_single],
        "candidates": list(candidates),
        "weights": [1.0],
        "ensemble": ensemble,
        "selection_metrics": {
            "best_single": classification_metrics(y_select, calibrated[best_single]),
            "ensemble": ensemble_metrics,
        },
        "calibrated_select": calibrated,
    }


def _final_test(
    dataset: FootballDataset,
    plan: TemporalSplitPlan,
    fitted: dict[str, Any],
    calibration: dict[str, Any],
    ensemble_decision: dict[str, Any],
) -> dict[str, Any]:
    calib_index = plan.calibration_fit.index.append(plan.calibration_select.index)
    y_calib = dataset.labels(calib_index)
    y_test = dataset.labels(plan.test.index)
    calibrators: dict[str, ProbabilityCalibrator] = {}
    test_proba: dict[str, np.ndarray] = {}
    public_models: dict[str, Any] = {}
    for name, model in fitted.items():
        method = calibration["selected_method"][name]
        calibrator = make_calibrator(method)
        raw_calib = model.predict_clipped(dataset, calib_index)
        if method != "raw":
            calibrator.fit(raw_calib, y_calib)
        calibrators[name] = calibrator
        proba = calibrator.transform(model.predict_clipped(dataset, plan.test.index))
        test_proba[name] = proba
        metrics = classification_metrics(y_test, proba)
        public_models[name] = {
            "calibration_method": method,
            "metrics": metrics,
            "reliability": reliability_table(y_test, proba),
            "by_competition": grouped_metrics(dataset.frame, plan.test.index, y_test, proba, "competition_id"),
            "by_season": grouped_metrics(dataset.frame, plan.test.index, y_test, proba, "season"),
            "by_result": metrics["per_class"],
        }
    selected_name = ensemble_decision["registered_name"]
    if selected_name == "ensemble":
        ensemble: ProbabilityEnsemble = ensemble_decision["ensemble"]
        selected_proba = ensemble.combine({name: test_proba[name] for name in ensemble.members})
        selected_metrics = classification_metrics(y_test, selected_proba)
        public_models["ensemble"] = {
            "calibration_method": "memberwise_then_weighted_average",
            "members": list(ensemble.members),
            "weights": [float(value) for value in ensemble.weights],
            "metrics": selected_metrics,
            "reliability": reliability_table(y_test, selected_proba),
            "by_competition": grouped_metrics(dataset.frame, plan.test.index, y_test, selected_proba, "competition_id"),
            "by_season": grouped_metrics(dataset.frame, plan.test.index, y_test, selected_proba, "season"),
            "by_result": selected_metrics["per_class"],
        }
    else:
        selected_proba = test_proba[selected_name]
        selected_metrics = public_models[selected_name]["metrics"]
    return {
        "public": {
            "period": plan.test.to_dict(),
            "selection_rule": (
                "Walk-forward mean log-loss ranks models. Calibration method is chosen on "
                "calibration_select. Ensemble is kept only if it beats the best single model "
                "on calibration_select. The final test window is never used for selection."
            ),
            "models": public_models,
            "selected": selected_name,
            "selected_metrics": selected_metrics,
        },
        "calibrators": calibrators,
        "selected_test_proba": selected_proba,
    }


def _replay_test(dataset: FootballDataset, plan: TemporalSplitPlan, artefact: dict[str, Any]) -> np.ndarray:
    selected = artefact["selected"]
    predictors: dict[str, Any] = artefact["predictors"]
    calibrators: dict[str, ProbabilityCalibrator] = artefact["calibrators"]
    if selected == "ensemble":
        ensemble: ProbabilityEnsemble = artefact["ensemble"]
        member_proba = {
            name: calibrators[name].transform(predictors[name].predict_clipped(dataset, plan.test.index))
            for name in ensemble.members
        }
        return ensemble.combine(member_proba)
    model = predictors[selected]
    return calibrators[selected].transform(model.predict_clipped(dataset, plan.test.index))


def _registry_card(
    dataset: FootballDataset,
    plan: TemporalSplitPlan,
    walk_forward: dict[str, Any],
    calibration: dict[str, Any],
    ensemble_decision: dict[str, Any],
    test_report: dict[str, Any],
    robustness: dict[str, Any],
    fitted: dict[str, Any],
) -> RegistryCard:
    selected = ensemble_decision["registered_name"]
    features = list(BOOSTING_FEATURES)
    hyperparameters: dict[str, Any]
    if selected == "ensemble":
        hyperparameters = ensemble_decision["ensemble"].hyperparameters()
        hyperparameters["member_hyperparameters"] = {
            name: dict(fitted[name].hyperparameters()) for name in ensemble_decision["members"]
        }
        hyperparameters["member_calibration"] = {
            name: calibration["selected_method"][name] for name in ensemble_decision["members"]
        }
        calibration_method = "memberwise_then_weighted_average"
    else:
        hyperparameters = dict(fitted[selected].hyperparameters())
        features = {
            "frequency": [],
            "elo": list(ELO_FEATURES),
            "poisson": list(POISSON_FEATURES),
            "xgboost": list(BOOSTING_FEATURES),
            "lightgbm": list(BOOSTING_FEATURES),
        }[selected]
        calibration_method = calibration["selected_method"][selected]
    return RegistryCard(
        model_version=MODEL_VERSION,
        dataset_version=dataset.dataset_version,
        feature_schema_version=dataset.feature_schema_version,
        training_period=plan.final_train.to_dict(),
        validation_period={
            "calibration_fit": plan.calibration_fit.to_dict(),
            "calibration_select": plan.calibration_select.to_dict(),
        },
        test_period=plan.test.to_dict(),
        features=features,
        hyperparameters=hyperparameters,
        metrics={
            "walk_forward": {name: _compact_wf(walk_forward[name]) for name in MODEL_FACTORIES},
            "test": test_report["public"]["selected_metrics"],
            "test_all_models": {
                name: test_report["public"]["models"][name]["metrics"]
                for name in test_report["public"]["models"]
            },
        },
        calibration_method=calibration_method,
        random_seed=RANDOM_SEED,
        code_version=str(robustness["code_version"]),
        dataset_sha256=dataset.sha256,
        selected_model=selected,
        ensemble_used=bool(ensemble_decision["used"]),
        notes=[
            "Not connected to the backend.",
            "No live predictions.",
            "No odds, value, or EV.",
            "Final test was not used to choose hyperparameters or the registered model.",
        ],
    )


def _compact_wf(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mean_log_loss": payload["mean_log_loss"],
        "mean_brier_score": payload["mean_brier_score"],
        "mean_accuracy": payload["mean_accuracy"],
        "mean_ece": payload["mean_ece"],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    import json

    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default), encoding="utf-8")


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
