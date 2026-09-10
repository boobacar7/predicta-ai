from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, log_loss

from predicta_ml.constants import CALIBRATION_BINS, CLASS_LABELS, PROBABILITY_CLIP


def clip_proba(proba: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(proba, dtype=np.float64), PROBABILITY_CLIP, 1.0)
    totals = clipped.sum(axis=1, keepdims=True)
    return clipped / totals


def classification_metrics(y_true: np.ndarray, proba: np.ndarray) -> dict[str, Any]:
    probabilities = clip_proba(proba)
    labels = np.asarray(y_true, dtype=np.int64)
    predicted = probabilities.argmax(axis=1)
    one_hot = np.eye(3, dtype=np.float64)[labels]
    brier = float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))
    return {
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1, 2])),
        "brier_score": brier,
        "accuracy": float(np.mean(predicted == labels)),
        "n": int(labels.size),
        "ece": expected_calibration_error(labels, probabilities),
        "per_class": per_class_metrics(labels, probabilities),
        "confusion_matrix": confusion_matrix(labels, predicted, labels=[0, 1, 2]).tolist(),
        "confusion_matrix_labels": list(CLASS_LABELS),
        "predicted_distribution": _counts(predicted),
        "actual_distribution": _counts(labels),
    }


def per_class_metrics(y_true: np.ndarray, proba: np.ndarray) -> dict[str, dict[str, float]]:
    probabilities = clip_proba(proba)
    predicted = probabilities.argmax(axis=1)
    report: dict[str, dict[str, float]] = {}
    for index, label in enumerate(CLASS_LABELS):
        mask = y_true == index
        support = int(mask.sum())
        pred_mask = predicted == index
        true_positive = int(np.logical_and(mask, pred_mask).sum())
        precision = true_positive / int(pred_mask.sum()) if pred_mask.any() else 0.0
        recall = true_positive / support if support else 0.0
        p_class = np.clip(probabilities[:, index], PROBABILITY_CLIP, 1.0 - PROBABILITY_CLIP)
        y_class = (y_true == index).astype(np.float64)
        log_loss_class = float(-np.mean(y_class * np.log(p_class) + (1.0 - y_class) * np.log(1.0 - p_class)))
        report[label] = {
            "support": float(support),
            "precision": float(precision),
            "recall": float(recall),
            "mean_predicted_probability": float(probabilities[mask, index].mean()) if support else 0.0,
            "log_loss_ovr": log_loss_class,
            "brier": float(np.mean((probabilities[:, index] - y_class) ** 2)),
        }
    return report


def grouped_metrics(
    frame: pd.DataFrame,
    index: pd.Index,
    y_true: np.ndarray,
    proba: np.ndarray,
    column: str,
) -> dict[str, dict[str, Any]]:
    subset = frame.loc[index]
    report: dict[str, dict[str, Any]] = {}
    values = subset[column].astype(str).to_numpy()
    for key in sorted(set(values.tolist())):
        mask = values == key
        if int(mask.sum()) == 0:
            continue
        metrics = classification_metrics(y_true[mask], proba[mask])
        report[key] = {
            "n": metrics["n"],
            "log_loss": metrics["log_loss"],
            "brier_score": metrics["brier_score"],
            "accuracy": metrics["accuracy"],
            "ece": metrics["ece"],
        }
    return report


def expected_calibration_error(
    y_true: np.ndarray,
    proba: np.ndarray,
    bins: int = CALIBRATION_BINS,
) -> float:
    probabilities = clip_proba(proba)
    confidence = probabilities.max(axis=1)
    predicted = probabilities.argmax(axis=1)
    correct = (predicted == y_true).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    n = float(y_true.size)
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        if right == 1.0:
            mask = (confidence >= left) & (confidence <= right)
        else:
            mask = (confidence >= left) & (confidence < right)
        count = int(mask.sum())
        if count == 0:
            continue
        acc = float(correct[mask].mean())
        conf = float(confidence[mask].mean())
        ece += (count / n) * abs(acc - conf)
    return float(ece)


def reliability_table(y_true: np.ndarray, proba: np.ndarray, bins: int = CALIBRATION_BINS) -> list[dict[str, float]]:
    probabilities = clip_proba(proba)
    confidence = probabilities.max(axis=1)
    predicted = probabilities.argmax(axis=1)
    correct = (predicted == y_true).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float]] = []
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        if right == 1.0:
            mask = (confidence >= left) & (confidence <= right)
        else:
            mask = (confidence >= left) & (confidence < right)
        count = int(mask.sum())
        rows.append(
            {
                "bin_left": float(left),
                "bin_right": float(right),
                "count": float(count),
                "accuracy": float(correct[mask].mean()) if count else 0.0,
                "confidence": float(confidence[mask].mean()) if count else 0.0,
            }
        )
    return rows


def core_metrics(y_true: np.ndarray, proba: np.ndarray) -> dict[str, float | int]:
    metrics = classification_metrics(y_true, proba)
    return {
        "n": int(metrics["n"]),
        "log_loss": float(metrics["log_loss"]),
        "brier_score": float(metrics["brier_score"]),
        "accuracy": float(metrics["accuracy"]),
        "ece": float(metrics["ece"]),
    }


def class_reliability_table(
    y_true: np.ndarray,
    proba: np.ndarray,
    klass: int,
    bins: int = CALIBRATION_BINS,
) -> list[dict[str, float]]:
    probabilities = clip_proba(proba)
    scores = probabilities[:, klass]
    observed = (y_true == klass).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float]] = []
    for left, right in zip(edges[:-1], edges[1:], strict=True):
        if right == 1.0:
            mask = (scores >= left) & (scores <= right)
        else:
            mask = (scores >= left) & (scores < right)
        count = int(mask.sum())
        rows.append(
            {
                "bin_left": float(left),
                "bin_right": float(right),
                "count": float(count),
                "observed_frequency": float(observed[mask].mean()) if count else 0.0,
                "mean_predicted": float(scores[mask].mean()) if count else 0.0,
            }
        )
    return rows


def class_ece(y_true: np.ndarray, proba: np.ndarray, klass: int, bins: int = CALIBRATION_BINS) -> float:
    rows = class_reliability_table(y_true, proba, klass, bins=bins)
    n = float(y_true.size)
    if n == 0:
        return 0.0
    return float(sum((row["count"] / n) * abs(row["observed_frequency"] - row["mean_predicted"]) for row in rows))


def _counts(labels: np.ndarray) -> dict[str, int]:
    return {name: int((labels == index).sum()) for index, name in enumerate(CLASS_LABELS)}
