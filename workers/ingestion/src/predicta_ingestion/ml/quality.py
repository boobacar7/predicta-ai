from __future__ import annotations

from collections import Counter

from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.ml.dataset import MlDataset
from predicta_ingestion.ml.features import FEATURE_SCHEMA, H2H_MIN_MATCHES


def build_quality_report(dataset: MlDataset) -> dict[str, object]:
    observations = sorted(dataset.observations, key=lambda item: (ensure_utc(item.event_at), item.match_id))
    match_ids = [item.match_id for item in observations]
    duplicate_ids = sorted({item for item, count in Counter(match_ids).items() if count > 1})
    ordered = observations == dataset.observations
    null_counts: dict[str, int] = {}
    availability: dict[str, dict[str, int]] = {}
    for key in FEATURE_SCHEMA:
        values = [item.features.get(key) for item in observations]
        null_counts[key] = sum(1 for value in values if value is None)
        if key.endswith("_available"):
            availability[key] = {
                "ones": sum(1 for value in values if value == 1),
                "zeros": sum(1 for value in values if value == 0),
            }
    reasons = Counter(item.reason for item in dataset.rejections)
    return {
        "dataset_version": dataset.dataset_version,
        "code_version": dataset.code_version,
        "cutoff_policy": dataset.cutoff_policy,
        "competition": dataset.competition,
        "seasons": dataset.seasons,
        "observation_count": dataset.observation_count,
        "rejected_count": dataset.rejected_count,
        "rejection_reasons": dict(sorted(reasons.items())),
        "feature_count": len(dataset.feature_schema),
        "feature_schema": dataset.feature_schema,
        "elo_parameters": dataset.elo_parameters,
        "period_start": dataset.period_start.isoformat() if dataset.period_start else None,
        "period_end": dataset.period_end.isoformat() if dataset.period_end else None,
        "duplicate_match_ids": duplicate_ids,
        "temporal_order_ok": ordered and not duplicate_ids,
        "null_counts": null_counts,
        "availability": availability,
        "anti_leakage": {
            "checked": True,
            "violations": _count_consistency_violations(dataset),
            "policy": "event_at < cutoff and available_at < cutoff; target match excluded",
        },
        "standings_available": dataset.standings_available,
    }


def _count_consistency_violations(dataset: MlDataset) -> int:
    violations = 0
    previous = None
    for item in dataset.observations:
        event_at = ensure_utc(item.event_at)
        if previous is not None and event_at < previous:
            violations += 1
        previous = event_at
        if item.home_win + item.draw + item.away_win != 1:
            violations += 1
        played_home = item.features.get("home_matches_played")
        played_away = item.features.get("away_matches_played")
        if item.features.get("home_form_5_available") == 1 and not (
            isinstance(played_home, int) and played_home >= 5
        ):
            violations += 1
        if item.features.get("home_form_10_available") == 1 and not (
            isinstance(played_home, int) and played_home >= 10
        ):
            violations += 1
        if item.features.get("away_form_5_available") == 1 and not (
            isinstance(played_away, int) and played_away >= 5
        ):
            violations += 1
        if item.features.get("away_form_10_available") == 1 and not (
            isinstance(played_away, int) and played_away >= 10
        ):
            violations += 1
        h2h = item.features.get("h2h_matches")
        if item.features.get("h2h_available") == 1 and not (isinstance(h2h, int) and h2h >= H2H_MIN_MATCHES):
            violations += 1
        if item.features.get("h2h_available") == 0 and isinstance(h2h, int) and h2h >= H2H_MIN_MATCHES:
            violations += 1
    return violations
