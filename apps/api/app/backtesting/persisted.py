from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.ai_picks.models import AiPicksQuery
from app.ai_picks.service import AiPicksEngine
from app.backtesting.fixture_universe import (
    LIVE_COMPETITIONS,
    LIVE_WEEKEND_CLOCK,
    LIVE_WEEKEND_END,
    LIVE_WEEKEND_START,
)
from app.backtesting.pilot import (
    VALUE_SNAPSHOT_RULE,
    WEEKEND_IDENTITY_EXCLUSIONS,
    CatalogCandidateSource,
    CatalogIdentityRepository,
    PilotServices,
    _settle_argmax,
    _settle_naive,
    _settle_picks,
    selected_snapshot_is_pit_safe,
    value_parity_errors,
)
from app.backtesting.types import CatalogMatch, QualityExclusion, QualityLedger
from app.core.clock import Clock
from app.odds.providers import LiveOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import DataMode, Football1x2Selection, OddsSelection, OddsSnapshot, is_complete_football_1x2
from app.predictions.runtime import ensure_ml_on_path
from app.predictions.service import FootballPredictionService, build_football_prediction_service
from app.predictions.types import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS
from app.value_engine.calculator import VALUE_ENGINE_VERSION
from app.value_engine.models import FootballValueAnalysis
from app.value_engine.service import FootballValueService

ensure_ml_on_path()
from predicta_ml.backtesting.value_metrics import (  # noqa: E402
    INSUFFICIENT_SAMPLE_N,
    SAMPLE_WARNING,
    strategy_metrics,
)
from predicta_ml.constants import CANDIDATE_STATUS as ML_CANDIDATE_STATUS  # noqa: E402
from predicta_ml.features.dataset import load_football_dataset  # noqa: E402


def api_snapshot_from_ingestion(snapshot: Any) -> OddsSnapshot:
    """Map a persisted canonical odds snapshot onto the API OddsSnapshot contract."""

    provenance = snapshot.provenance
    available_at = provenance.available_at
    collected_at = provenance.collected_at
    if available_at < collected_at:
        raise ValueError(
            "Persisted snapshot available_at is before collected_at; timestamps are never rewritten."
        )
    selections = tuple(
        OddsSelection(Football1x2Selection(item.selection), item.decimal_odds)
        for item in snapshot.selections
    )
    return OddsSnapshot(
        id=str(snapshot.id),
        provider_id=str(provenance.provider_id),
        match_id=str(snapshot.match_id),
        bookmaker=str(snapshot.bookmaker),
        market=str(snapshot.market),
        selections=selections,
        collected_at=collected_at,
        available_at=available_at,
        source=str(provenance.source),
        data_mode=_data_mode(provenance.data_mode),
        raw_payload_id=provenance.raw_payload_id,
    )


def _data_mode(value: object) -> DataMode:
    raw = getattr(value, "value", value)
    if raw == "live":
        return "live"
    if raw == "mock":
        return "mock"
    raise ValueError(f"Unsupported data_mode: {raw!r}")


def weekend_catalog_from_parquet(
    dataset_path: Path,
    *,
    names: dict[str, tuple[str, str]] | None = None,
) -> tuple[CatalogMatch, ...]:
    dataset = load_football_dataset(dataset_path)
    frame = dataset.frame
    window = frame[
        (frame["event_at"] >= LIVE_WEEKEND_START)
        & (frame["event_at"] < LIVE_WEEKEND_END)
        & (frame["competition"].astype(str).isin(LIVE_COMPETITIONS))
    ].sort_values(["event_at", "match_id"])
    catalog: list[CatalogMatch] = []
    aliases = names or {}
    for _, raw in window.iterrows():
        match_id = str(raw["match_id"])
        home_id = str(raw["home_team_id"])
        away_id = str(raw["away_team_id"])
        home_name, away_name = aliases.get(match_id, (home_id, away_id))
        catalog.append(
            CatalogMatch(
                match_id=match_id,
                home_team_id=home_id,
                away_team_id=away_id,
                home_team=home_name,
                away_team=away_name,
                league=str(raw["competition"]),
                kickoff_at=raw["event_at"].to_pydatetime(),
                outcome=str(raw["target"]),
                home_elo_pre=float(raw["home_elo_pre"]),
                away_elo_pre=float(raw["away_elo_pre"]),
            )
        )
    return tuple(catalog)


def build_persisted_services(
    catalog: tuple[CatalogMatch, ...],
    snapshots: tuple[OddsSnapshot, ...],
    *,
    predictions: FootballPredictionService,
    clock: Clock | None = None,
) -> PilotServices:
    active_clock = clock or Clock(LIVE_WEEKEND_CLOCK)
    odds = OddsService(
        provider=LiveOddsProvider(enable_live=True, snapshots=snapshots),
        repository=InMemoryOddsRepository(),
    )
    values = FootballValueService(clock=active_clock, predictions=predictions, odds=odds)
    picks = AiPicksEngine(
        values=values,
        candidates=CatalogCandidateSource(catalog),
        thresholds=AiPicksThresholds(),
    )
    return PilotServices(
        clock=active_clock,
        predictions=predictions,
        values=values,
        picks=picks,
        odds=odds,
        identities=CatalogIdentityRepository(catalog),
    )


def run_persisted_weekend_pilot(
    *,
    catalog: tuple[CatalogMatch, ...],
    snapshots: tuple[OddsSnapshot, ...],
    predictions: FootballPredictionService | None = None,
    dataset_path: Path | None = None,
    registry_dir: Path | None = None,
    persist_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score the 21-24 Aug 2026 weekend with persisted PIT odds. Does not tune thresholds."""

    clock = Clock(LIVE_WEEKEND_CLOCK)
    predictor = predictions
    if predictor is None:
        if dataset_path is None or registry_dir is None:
            raise ValueError("Persisted weekend scoring needs a predictor or parquet + registry.")
        predictor = build_football_prediction_service(
            clock=clock,
            registry_dir=registry_dir,
            dataset_path=dataset_path,
            model_version=CANDIDATE_MODEL_VERSION,
        )
    first = _evaluate_persisted(catalog, snapshots, predictor, clock)
    second = _evaluate_persisted(catalog, snapshots, predictor, clock)
    first["reproducibility"] = {
        "passed": first["fingerprint"] == second["fingerprint"],
        "first": first["fingerprint"],
        "second": second["fingerprint"],
    }
    first["persist"] = persist_meta or {}
    first["verdict"] = _verdict(first)
    return first


def _evaluate_persisted(
    catalog: tuple[CatalogMatch, ...],
    snapshots: tuple[OddsSnapshot, ...],
    predictions: FootballPredictionService,
    clock: Clock,
) -> dict[str, Any]:
    eligible_catalog = tuple(item for item in catalog if item.match_id not in WEEKEND_IDENTITY_EXCLUSIONS)
    scoring_snapshots = tuple(item for item in snapshots if item.match_id not in WEEKEND_IDENTITY_EXCLUSIONS)
    services = build_persisted_services(
        eligible_catalog,
        scoring_snapshots,
        predictions=predictions,
        clock=clock,
    )
    by_id = {item.match_id: item for item in catalog}
    quality = QualityLedger()
    quality.snapshots_accepted = sum(1 for item in scoring_snapshots if is_complete_football_1x2(item))
    quality.bookmakers_seen = sorted({item.bookmaker for item in scoring_snapshots})
    analyses: dict[str, FootballValueAnalysis] = {}
    parity_errors: list[str] = []
    pit_ok = True
    rows: list[dict[str, Any]] = []
    scored = list(eligible_catalog)
    for match in catalog:
        identity_exclusion = WEEKEND_IDENTITY_EXCLUSIONS.get(match.match_id)
        if identity_exclusion is not None:
            kind = "isolated_team" if identity_exclusion.startswith("isolated_team") else "inverted_home_away"
            quality.add(
                QualityExclusion(
                    kind=kind,  # type: ignore[arg-type]
                    detail=identity_exclusion,
                    match_id=match.match_id,
                )
            )
            rows.append(_match_row(match, None, identity_exclusion=identity_exclusion))
            continue
        try:
            analysis = services.values.evaluate(match.match_id, match.kickoff_at)
        except Exception as exc:
            quality.add(
                QualityExclusion(
                    kind="odds_unavailable",
                    detail=str(exc),
                    match_id=match.match_id,
                )
            )
            prediction = services.predictions.predict(match.match_id, match.kickoff_at)
            rows.append(_match_row(match, None, prediction=prediction, identity_exclusion=None))
            continue
        analyses[match.match_id] = analysis
        if not selected_snapshot_is_pit_safe(analysis.odds.available_at, match.kickoff_at):
            pit_ok = False
        parity_errors.extend(value_parity_errors(analysis))
        rows.append(_match_row(match, analysis, identity_exclusion=None))

    picks = services.picks.list_picks(
        AiPicksQuery(match_date=None, league=None, limit=200, offset=0, minimum_edge=None, minimum_ev=None)
    )
    settled_picks = _settle_picks(picks.items, by_id)
    matched_with_value = [item for item in scored if item.match_id in analyses]
    elo_value_bets = _settle_argmax(matched_with_value, analyses, strategy="elo_no_value_filter")
    naive_bets = _settle_naive(matched_with_value, analyses, selection="HOME", strategy="naive_home")
    elo_model_metrics = _model_argmax_metrics(scored, services)

    pick_metrics = strategy_metrics(settled_picks)
    elo_value_metrics = strategy_metrics(elo_value_bets)
    naive_metrics = strategy_metrics(naive_bets)
    fingerprint = {
        "predictions": {
            match_id: (
                analysis.prediction.home_probability,
                analysis.prediction.draw_probability,
                analysis.prediction.away_probability,
            )
            for match_id, analysis in sorted(analyses.items())
        },
        "books": {match_id: analysis.odds.bookmaker for match_id, analysis in sorted(analyses.items())},
        "picks": [(item.match_id, item.selection, item.rank) for item in picks.items],
        "roi": pick_metrics["theoretical_roi"],
        "hit_rate": pick_metrics["hit_rate"],
    }
    n_picks = pick_metrics["n"]
    return {
        "kind": "persisted_live_weekend",
        "model_version": CANDIDATE_MODEL_VERSION,
        "model_status": CANDIDATE_STATUS,
        "value_engine_version": VALUE_ENGINE_VERSION,
        "ai_picks_version": AI_PICKS_VERSION,
        "bookmaker_policy": VALUE_SNAPSHOT_RULE,
        "candidate_promoted": False,
        "thresholds": {
            "minimum_edge": 0.0,
            "minimum_ev": 0.0,
            "minimum_model_probability": 0.0,
            "maximum_odds_age_seconds": 24 * 3600,
            "optimized_on_test": False,
        },
        "dataset": {
            "matches": len(catalog),
            "identity_matched": len(scored),
            "identity_rejected": len(WEEKEND_IDENTITY_EXCLUSIONS),
            "predictions": len(scored),
            "matches_with_odds": len(analyses),
            "value_eligible": len(matched_with_value),
            "eligible_ai_picks": n_picks,
            "snapshots": quality.snapshots_accepted,
        },
        "quality": {
            "snapshots_accepted": quality.snapshots_accepted,
            "matches_without_odds": quality.matches_without_odds,
            "bookmakers": list(quality.bookmakers_seen),
            "exclusions": [
                {
                    "kind": item.kind,
                    "detail": item.detail,
                    "event_id": item.event_id,
                    "match_id": item.match_id,
                    "bookmaker": item.bookmaker,
                    "selection": item.selection,
                }
                for item in quality.exclusions
            ],
        },
        "rows": rows,
        "model_performance": elo_model_metrics,
        "value_performance": elo_value_metrics,
        "ai_picks_performance": pick_metrics,
        "baselines": {
            "naive_home": naive_metrics,
            "elo_no_value_filter": elo_value_metrics,
            "ai_picks_value": pick_metrics,
            "same_match_set": True,
            "match_set": "identity_matched_matches_with_value_odds",
        },
        "pit": {
            "passed": pit_ok,
            "rule": (
                "Odds: available_at <= kickoff via OddsService / value-engine-0.1. "
                "event_at identifies the match and does not exclude pre-match odds. "
                "ML features keep event_at < cutoff and available_at < cutoff."
            ),
        },
        "value_parity": {"passed": not parity_errors, "errors": parity_errors},
        "ai_picks_parity": {
            "passed": AI_PICKS_VERSION == "ai-picks-0.1" and VALUE_ENGINE_VERSION == "value-engine-0.1",
            "version": AI_PICKS_VERSION,
        },
        "fingerprint": fingerprint,
        "sample_warning": SAMPLE_WARNING if n_picks < INSUFFICIENT_SAMPLE_N else None,
        "ai_picks_exclusions": [
            {
                "match_id": item.match_id,
                "selection": item.selection,
                "reason": item.reason.value,
                "detail": item.detail,
            }
            for item in picks.exclusions
        ],
        "ml_candidate_status": ML_CANDIDATE_STATUS,
        "source": LIVE_ODDS_SOURCE,
    }


def _model_argmax_metrics(matches: list[CatalogMatch], services: PilotServices) -> dict[str, Any]:
    n = len(matches)
    if n == 0:
        return {
            "n": 0,
            "hits": 0,
            "hit_rate": None,
            "home": 0,
            "draw": 0,
            "away": 0,
            "sample_warning": SAMPLE_WARNING,
            "note": "Model argmax accuracy on identity-matched matches. Not a betting ROI.",
        }
    hits = 0
    counts = {"HOME": 0, "DRAW": 0, "AWAY": 0}
    for match in matches:
        prediction = services.predictions.predict(match.match_id, match.kickoff_at)
        probs = {
            "HOME": prediction.home_probability,
            "DRAW": prediction.draw_probability,
            "AWAY": prediction.away_probability,
        }
        selection = max(probs, key=lambda name: (probs[name], name))
        counts[selection] += 1
        hits += int(selection == match.outcome)
    return {
        "n": n,
        "hits": hits,
        "hit_rate": hits / n,
        "home": counts["HOME"],
        "draw": counts["DRAW"],
        "away": counts["AWAY"],
        "sample_warning": SAMPLE_WARNING if n < INSUFFICIENT_SAMPLE_N else None,
        "note": "Model argmax accuracy on identity-matched matches. Not a betting ROI.",
    }


def _match_row(
    match: CatalogMatch,
    analysis: FootballValueAnalysis | None,
    *,
    identity_exclusion: str | None,
    prediction: Any | None = None,
) -> dict[str, Any]:
    pred = analysis.prediction if analysis is not None else prediction
    odds_age = None
    if analysis is not None:
        odds_age = (match.kickoff_at - analysis.odds.available_at).total_seconds()
    return {
        "match_id": match.match_id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "league": match.league,
        "kickoff_at": match.kickoff_at.isoformat(),
        "outcome": match.outcome,
        "identity_exclusion": identity_exclusion,
        "home_probability": None if pred is None else pred.home_probability,
        "draw_probability": None if pred is None else pred.draw_probability,
        "away_probability": None if pred is None else pred.away_probability,
        "bookmaker": None if analysis is None else analysis.odds.bookmaker,
        "available_at": None if analysis is None else analysis.odds.available_at.isoformat(),
        "odds_age_seconds": odds_age,
        "home_odds": None if analysis is None else analysis.odds.home_odds,
        "draw_odds": None if analysis is None else analysis.odds.draw_odds,
        "away_odds": None if analysis is None else analysis.odds.away_odds,
        "home_implied": None if analysis is None else analysis.market_probabilities.home.implied_probability,
        "draw_implied": None if analysis is None else analysis.market_probabilities.draw.implied_probability,
        "away_implied": None if analysis is None else analysis.market_probabilities.away.implied_probability,
        "home_no_vig": None if analysis is None else analysis.market_probabilities.home.no_vig_probability,
        "draw_no_vig": None if analysis is None else analysis.market_probabilities.draw.no_vig_probability,
        "away_no_vig": None if analysis is None else analysis.market_probabilities.away.no_vig_probability,
        "home_edge": None if analysis is None else analysis.value.home.edge,
        "draw_edge": None if analysis is None else analysis.value.draw.edge,
        "away_edge": None if analysis is None else analysis.value.away.edge,
        "home_ev": None if analysis is None else analysis.value.home.ev,
        "draw_ev": None if analysis is None else analysis.value.draw.ev,
        "away_ev": None if analysis is None else analysis.value.away.ev,
    }


def _verdict(report: dict[str, Any]) -> str:
    if (
        not report["pit"]["passed"]
        or not report["value_parity"]["passed"]
        or not report["reproducibility"]["passed"]
        or not report["ai_picks_parity"]["passed"]
    ):
        return "NO-GO"
    if report["dataset"]["matches_with_odds"] < report["dataset"]["identity_matched"]:
        return "GO WITH CONDITIONS"
    return "GO WITH CONDITIONS"
