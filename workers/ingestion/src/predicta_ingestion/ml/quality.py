from __future__ import annotations

from collections import Counter
from statistics import fmean

from predicta_ingestion.clock import ensure_utc
from predicta_ingestion.ml.dataset import MlDataset
from predicta_ingestion.ml.elo import reconstruct_pre_match_elo
from predicta_ingestion.ml.features import FEATURE_SCHEMA, H2H_MIN_MATCHES, prior_matches_for_features
from predicta_ingestion.pit.store import PointInTimeStore


def build_quality_report(dataset: MlDataset, store: PointInTimeStore | None = None) -> dict[str, object]:
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
    home_wins = sum(item.home_win for item in observations)
    draws = sum(item.draw for item in observations)
    away_wins = sum(item.away_win for item in observations)
    teams = {team_id for item in observations for team_id in (item.home_team_id, item.away_team_id) if team_id}
    same_ts = Counter(ensure_utc(item.event_at).isoformat() for item in observations)
    tied_groups = {stamp: count for stamp, count in same_ts.items() if count > 1}
    consistency = _count_consistency_violations(dataset)
    pit = _point_in_time_checks(dataset, store) if store is not None else None
    return {
        "dataset_version": dataset.dataset_version,
        "feature_schema_version": dataset.feature_schema_version,
        "code_version": dataset.code_version,
        "cutoff_policy": dataset.cutoff_policy,
        "source": dataset.source,
        "generated_at": dataset.generated_at.isoformat(),
        "competition": dataset.competition,
        "competitions": dataset.competitions,
        "seasons": dataset.seasons,
        "observation_count": dataset.observation_count,
        "rejected_count": dataset.rejected_count,
        "rejection_reasons": dict(sorted(reasons.items())),
        "feature_count": len(dataset.feature_schema),
        "feature_schema": dataset.feature_schema,
        "elo_parameters": dataset.elo_parameters,
        "period_start": dataset.period_start.isoformat() if dataset.period_start else None,
        "period_end": dataset.period_end.isoformat() if dataset.period_end else None,
        "team_count": len(teams),
        "competition_count": len(dataset.competitions),
        "season_count": len(dataset.seasons),
        "duplicate_match_ids": duplicate_ids,
        "temporal_order_ok": ordered and not duplicate_ids,
        "chronological": {
            "sorted": ordered,
            "violations": consistency["chronological_violations"],
        },
        "target_distribution": {
            "home_win": home_wins,
            "draw": draws,
            "away_win": away_wins,
            "home_win_rate": _rate(home_wins, dataset.observation_count),
            "draw_rate": _rate(draws, dataset.observation_count),
            "away_win_rate": _rate(away_wins, dataset.observation_count),
        },
        "elo_stats": _elo_stats(dataset),
        "null_counts": null_counts,
        "availability": availability,
        "identical_timestamps": {
            "groups": len(tied_groups),
            "matches": sum(tied_groups.values()),
            "policy": (
                "Equal timestamps are ordered by (timestamp, kind, match_id); "
                "snapshot kind=0 runs before update kind=1. If available_at of A "
                "is >= kickoff of B, A's result does not change B's pre-match Elo."
            ),
        },
        "anti_leakage": {
            "checked": True,
            "violations": consistency["total"],
            "policy": "event_at < cutoff and available_at < cutoff; target match excluded",
            "target_one_hot_ok": consistency["target_violations"] == 0,
            "form_flags_ok": consistency["form_violations"] == 0,
            "h2h_flags_ok": consistency["h2h_violations"] == 0,
            "elo_diff_ok": consistency["elo_violations"] == 0,
            "point_in_time": pit,
        },
        "standings_available": False,
        "standings_used": False,
    }


def _point_in_time_checks(dataset: MlDataset, store: PointInTimeStore) -> dict[str, object]:
    rolling_self = 0
    rolling_future = 0
    available_at_violations = 0
    event_at_violations = 0
    h2h_future = 0
    elo_mismatches = 0
    same_timestamp_leaks = 0
    elo = reconstruct_pre_match_elo(list(store._sink.matches.values()))
    by_kickoff: dict[str, list[str]] = {}
    for item in dataset.observations:
        cutoff = ensure_utc(item.event_at)
        prior = prior_matches_for_features(store, store._sink.matches[item.match_id])
        prior_ids = {row.id for row in prior}
        if item.match_id in prior_ids:
            rolling_self += 1
        for row in prior:
            if ensure_utc(row.kickoff_at) >= cutoff:
                rolling_future += 1
            if ensure_utc(row.provenance.available_at) >= cutoff:
                available_at_violations += 1
            event_at = row.provenance.event_at or row.kickoff_at
            if ensure_utc(event_at) >= cutoff:
                event_at_violations += 1
            teams = {row.home_team_id, row.away_team_id}
            if teams == {item.home_team_id, item.away_team_id} and ensure_utc(row.kickoff_at) >= cutoff:
                h2h_future += 1
        expected = elo.get(item.match_id)
        if expected is None:
            elo_mismatches += 1
        else:
            home_elo = item.features.get("home_elo_pre")
            away_elo = item.features.get("away_elo_pre")
            if home_elo != expected[0] or away_elo != expected[1]:
                elo_mismatches += 1
        by_kickoff.setdefault(cutoff.isoformat(), []).append(item.match_id)
    for match_ids in by_kickoff.values():
        if len(match_ids) < 2:
            continue
        snapshots = [elo.get(match_id) for match_id in match_ids]
        if any(row is None for row in snapshots):
            same_timestamp_leaks += 1
    return {
        "target_excluded_from_rolling": rolling_self == 0,
        "rolling_future_matches": rolling_future,
        "available_at_violations": available_at_violations,
        "event_at_violations": event_at_violations,
        "h2h_future_matches": h2h_future,
        "elo_snapshot_mismatches": elo_mismatches,
        "identical_timestamp_snapshot_errors": same_timestamp_leaks,
        "ok": (
            rolling_self == 0
            and rolling_future == 0
            and available_at_violations == 0
            and event_at_violations == 0
            and h2h_future == 0
            and elo_mismatches == 0
            and same_timestamp_leaks == 0
        ),
    }


def _count_consistency_violations(dataset: MlDataset) -> dict[str, int]:
    chronological = 0
    target = 0
    form = 0
    h2h = 0
    elo = 0
    previous = None
    for item in dataset.observations:
        event_at = ensure_utc(item.event_at)
        if previous is not None and event_at < previous:
            chronological += 1
        previous = event_at
        if item.home_win + item.draw + item.away_win != 1:
            target += 1
        played_home = item.features.get("home_matches_played")
        played_away = item.features.get("away_matches_played")
        if item.features.get("home_form_5_available") == 1 and not (isinstance(played_home, int) and played_home >= 5):
            form += 1
        if item.features.get("home_form_10_available") == 1 and not (
            isinstance(played_home, int) and played_home >= 10
        ):
            form += 1
        if item.features.get("away_form_5_available") == 1 and not (isinstance(played_away, int) and played_away >= 5):
            form += 1
        if item.features.get("away_form_10_available") == 1 and not (
            isinstance(played_away, int) and played_away >= 10
        ):
            form += 1
        h2h_matches = item.features.get("h2h_matches")
        if item.features.get("h2h_available") == 1 and not (
            isinstance(h2h_matches, int) and h2h_matches >= H2H_MIN_MATCHES
        ):
            h2h += 1
        if item.features.get("h2h_available") == 0 and isinstance(h2h_matches, int) and h2h_matches >= H2H_MIN_MATCHES:
            h2h += 1
        home_elo = item.features.get("home_elo_pre")
        away_elo = item.features.get("away_elo_pre")
        elo_diff = item.features.get("elo_diff")
        if home_elo is not None and away_elo is not None and elo_diff != home_elo - away_elo:
            elo += 1
    return {
        "chronological_violations": chronological,
        "target_violations": target,
        "form_violations": form,
        "h2h_violations": h2h,
        "elo_violations": elo,
        "total": chronological + target + form + h2h + elo,
    }


def _elo_stats(dataset: MlDataset) -> dict[str, object]:
    return {
        "home_elo_pre": _numeric_stats([item.features.get("home_elo_pre") for item in dataset.observations]),
        "away_elo_pre": _numeric_stats([item.features.get("away_elo_pre") for item in dataset.observations]),
        "elo_diff": _numeric_stats([item.features.get("elo_diff") for item in dataset.observations]),
    }


def _numeric_stats(values: list[object]) -> dict[str, float | int | None]:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "mean": fmean(numbers),
    }


def _rate(count: int, total: int) -> float | None:
    if total == 0:
        return None
    return count / total
