from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.ai_analyst.service import FootballAnalystService
from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.ai_picks.models import AiPicksQuery, MatchCandidate
from app.ai_picks.service import AiPicksEngine
from app.backtesting.fixture_universe import (
    FIXTURE_CATALOG,
    FIXTURE_CLOCK,
    LIVE_COMPETITIONS,
    LIVE_WEEKEND_CLOCK,
    LIVE_WEEKEND_END,
    LIVE_WEEKEND_START,
    STUB_PROBABILITIES,
    historical_odds_fixture_paths,
)
from app.backtesting.odds_loader import inverted_psg_rennes_event, load_fixture_odds
from app.backtesting.types import (
    BookmakerDescriptiveRow,
    CatalogMatch,
    OddsBundle,
    QualityExclusion,
)
from app.core.clock import Clock
from app.match_identity.models import MatchIdentity
from app.odds.providers import LiveOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection, OddsSnapshot, is_complete_football_1x2
from app.predictions.features import InMemoryPitFeatureStore
from app.predictions.runtime import ensure_ml_on_path
from app.predictions.service import FootballPredictionService, build_football_prediction_service
from app.predictions.types import (
    CANDIDATE_MODEL_VERSION,
    CANDIDATE_STATUS,
    ModelStatus,
    OutcomeProbabilities,
    PitEloFeatures,
)
from app.value_engine.calculator import (
    VALUE_ENGINE_VERSION,
    edge,
    expected_value,
    implied_probability,
    no_vig_probabilities,
)
from app.value_engine.models import FootballValueAnalysis
from app.value_engine.service import FootballValueService

ensure_ml_on_path()
from predicta_ml.backtesting.value_metrics import (  # noqa: E402
    INSUFFICIENT_SAMPLE_N,
    SAMPLE_WARNING,
    SettledBet,
    settle_decimal,
    strategy_metrics,
)
from predicta_ml.constants import CANDIDATE_STATUS as ML_CANDIDATE_STATUS  # noqa: E402
from predicta_ml.constants import CLASS_LABELS  # noqa: E402

VALUE_SNAPSHOT_RULE = (
    "Last complete 1X2 snapshot with available_at <= cutoff, ordered by "
    "(available_at, collected_at, snapshot.id). Bookmaker identity is not a "
    "selection criterion; Pinnacle is not preferred because it looks better."
)
WEEKEND_IDENTITY_EXCLUSIONS = {
    "mth_football-sportmonks-19715629": "isolated_team: Paris / Paris FC / PSG kept distinct",
    "mth_football-sportmonks-19715631": "inverted_home_away: PSG/Rennes vs Rennes/PSG",
}
ISOLATED_PARIS_TEAM_ID = "tm_football-sportmonks-4508"


def catalog_identity_exclusions(catalog: tuple[CatalogMatch, ...]) -> dict[str, str]:
    """Paris FC isolation plus the labeled Rennes/PSG weekend exclusion. No HOME/AWAY flip."""

    exclusions = dict(WEEKEND_IDENTITY_EXCLUSIONS)
    for match in catalog:
        if match.home_team_id == ISOLATED_PARIS_TEAM_ID or match.away_team_id == ISOLATED_PARIS_TEAM_ID:
            exclusions[match.match_id] = "isolated_team: Paris / Paris FC / PSG kept distinct"
    return exclusions


SELECTIONS = (
    Football1x2Selection.HOME,
    Football1x2Selection.DRAW,
    Football1x2Selection.AWAY,
)


class StubCandidatePredictor:
    """Deterministic candidate-labelled predictor for CI. Not a second model."""

    def __init__(self, probabilities: dict[str, tuple[float, float, float]]) -> None:
        self._probabilities = probabilities

    @property
    def model_version(self) -> str:
        return CANDIDATE_MODEL_VERSION

    @property
    def model_status(self) -> ModelStatus:
        return CANDIDATE_STATUS

    @property
    def dataset_version(self) -> str:
        return "football-1x2-history-0.3"

    @property
    def feature_schema_version(self) -> str:
        return "football-1x2-features-0.3"

    def predict_1x2(self, features: PitEloFeatures) -> OutcomeProbabilities:
        home, draw, away = self._probabilities[features.match_id]
        return OutcomeProbabilities(home=home, draw=draw, away=away)


class CatalogIdentityRepository:
    def __init__(self, catalog: tuple[CatalogMatch, ...]) -> None:
        self._items = {item.match_id: item for item in catalog}

    def get(self, match_id: str) -> MatchIdentity | None:
        item = self._items.get(match_id)
        if item is None:
            return None
        return MatchIdentity(
            match_id=item.match_id,
            home_team_id=item.home_team_id,
            away_team_id=item.away_team_id,
            home_team=item.home_team,
            away_team=item.away_team,
            league=item.league,
            kickoff_at=item.kickoff_at,
            data_mode="live",
        )


class CatalogCandidateSource:
    def __init__(self, catalog: tuple[CatalogMatch, ...]) -> None:
        self._candidates = tuple(
            MatchCandidate(
                match_id=item.match_id,
                home_team_id=item.home_team_id,
                away_team_id=item.away_team_id,
                home_team=item.home_team,
                away_team=item.away_team,
                league=item.league,
                kickoff_at=item.kickoff_at,
            )
            for item in catalog
        )

    def list_candidates(self, *, match_date: date | None, league: str | None) -> list[MatchCandidate]:
        del match_date, league
        return list(self._candidates)


@dataclass(frozen=True)
class PilotServices:
    clock: Clock
    predictions: FootballPredictionService
    values: FootballValueService
    picks: AiPicksEngine
    odds: OddsService
    identities: CatalogIdentityRepository


def build_fixture_services(
    bundle: OddsBundle,
    catalog: tuple[CatalogMatch, ...],
    *,
    clock: Clock | None = None,
) -> PilotServices:
    active_clock = clock or Clock(FIXTURE_CLOCK)
    predictions = FootballPredictionService(
        clock=active_clock,
        features=InMemoryPitFeatureStore([item.pit_features() for item in catalog]),
        model=StubCandidatePredictor(STUB_PROBABILITIES),
    )
    odds = OddsService(
        provider=LiveOddsProvider(enable_live=True, snapshots=bundle.snapshots),
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


def value_parity_errors(analysis: FootballValueAnalysis) -> list[str]:
    errors: list[str] = []
    odds = {
        Football1x2Selection.HOME: Decimal(str(analysis.odds.home_odds)),
        Football1x2Selection.DRAW: Decimal(str(analysis.odds.draw_odds)),
        Football1x2Selection.AWAY: Decimal(str(analysis.odds.away_odds)),
    }
    probabilities = {
        Football1x2Selection.HOME: Decimal(str(analysis.prediction.home_probability)),
        Football1x2Selection.DRAW: Decimal(str(analysis.prediction.draw_probability)),
        Football1x2Selection.AWAY: Decimal(str(analysis.prediction.away_probability)),
    }
    no_vig, overround = no_vig_probabilities(odds)
    tolerance = Decimal("0.000000001")
    if analysis.metadata.value_engine_version != VALUE_ENGINE_VERSION:
        errors.append("value engine version mismatch")
    if abs(Decimal(str(analysis.market_probabilities.overround)) - overround) > tolerance:
        errors.append("overround mismatch")
    markets = {
        Football1x2Selection.HOME: analysis.market_probabilities.home,
        Football1x2Selection.DRAW: analysis.market_probabilities.draw,
        Football1x2Selection.AWAY: analysis.market_probabilities.away,
    }
    values = {
        Football1x2Selection.HOME: analysis.value.home,
        Football1x2Selection.DRAW: analysis.value.draw,
        Football1x2Selection.AWAY: analysis.value.away,
    }
    for selection in SELECTIONS:
        implied = implied_probability(odds[selection])
        expected_edge = edge(probabilities[selection], implied)
        expected_ev = expected_value(probabilities[selection], odds[selection])
        market = markets[selection]
        value = values[selection]
        if abs(Decimal(str(market.implied_probability)) - implied) > tolerance:
            errors.append(f"{selection.value} implied mismatch")
        if abs(Decimal(str(market.no_vig_probability)) - no_vig[selection]) > tolerance:
            errors.append(f"{selection.value} no-vig mismatch")
        if abs(Decimal(str(value.edge)) - expected_edge) > tolerance:
            errors.append(f"{selection.value} edge mismatch")
        if abs(Decimal(str(value.ev)) - expected_ev) > tolerance:
            errors.append(f"{selection.value} ev mismatch")
    return errors


def selected_snapshot_is_pit_safe(available_at: datetime, cutoff: datetime) -> bool:
    return available_at <= cutoff


def run_fixture_pilot(
    *,
    extra_events: list[dict[str, Any]] | None = None,
    catalog: tuple[CatalogMatch, ...] = FIXTURE_CATALOG,
) -> dict[str, Any]:
    extra = extra_events if extra_events is not None else [inverted_psg_rennes_event()]
    paths = historical_odds_fixture_paths()
    first = _evaluate_universe(load_fixture_odds(paths, catalog, extra_events=extra), catalog, Clock(FIXTURE_CLOCK))
    second = _evaluate_universe(load_fixture_odds(paths, catalog, extra_events=extra), catalog, Clock(FIXTURE_CLOCK))
    first["reproducibility"] = {
        "passed": first["fingerprint"] == second["fingerprint"],
        "first": first["fingerprint"],
        "second": second["fingerprint"],
    }
    first["api_credits"] = {"historical_data_already_available": True, "new_api_calls": 0, "new_credits": 0}
    first["verdict"] = _verdict(first)
    return first


def _evaluate_universe(bundle: OddsBundle, catalog: tuple[CatalogMatch, ...], clock: Clock) -> dict[str, Any]:
    services = build_fixture_services(bundle, catalog, clock=clock)
    by_id = {item.match_id: item for item in catalog}
    analyses: dict[str, FootballValueAnalysis] = {}
    parity_errors: list[str] = []
    pit_ok = True
    quality = bundle.quality
    for match in catalog:
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
            continue
        analyses[match.match_id] = analysis
        if analysis.odds.available_at > match.kickoff_at:
            pit_ok = False
        parity_errors.extend(value_parity_errors(analysis))

    picks = services.picks.list_picks(
        AiPicksQuery(match_date=None, league=None, limit=100, offset=0, minimum_edge=None, minimum_ev=None)
    )
    settled_picks = _settle_picks(picks.items, by_id)
    matched_with_value = [item for item in catalog if item.match_id in analyses]
    elo_bets = _settle_argmax(matched_with_value, analyses, strategy="elo_no_value_filter")
    naive_bets = _settle_naive(matched_with_value, analyses, selection="HOME", strategy="naive_home")
    descriptive_books = _bookmaker_descriptive(bundle.snapshots, analyses, matched_with_value)

    analyst_ok = False
    helix = analyses.get(catalog[0].match_id)
    if helix is not None:
        report = FootballAnalystService(
            clock=clock,
            identities=services.identities,
            predictions=services.predictions,
            values=services.values,
        ).explain(catalog[0].match_id, catalog[0].kickoff_at)
        analyst_ok = report.analyst.provider == "deterministic-v0.1" and report.value.availability == "available"

    pick_metrics = strategy_metrics(settled_picks)
    elo_metrics = strategy_metrics(elo_bets)
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
    findings = _findings(n_picks, pit_ok, not parity_errors, analyst_ok)
    return {
        "kind": "descriptive_fixture",
        "model_version": CANDIDATE_MODEL_VERSION,
        "model_status": CANDIDATE_STATUS,
        "value_engine_version": VALUE_ENGINE_VERSION,
        "ai_picks_version": AI_PICKS_VERSION,
        "bookmaker_policy": VALUE_SNAPSHOT_RULE,
        "thresholds": {
            "minimum_edge": 0.0,
            "minimum_ev": 0.0,
            "minimum_model_probability": 0.0,
            "maximum_odds_age_seconds": 24 * 3600,
            "optimized_on_test": False,
        },
        "dataset": {
            "matches": len(catalog),
            "events": quality.events,
            "matched": quality.matched,
            "rejected": quality.rejected,
            "snapshots": quality.snapshots_accepted,
            "predictions": len(analyses),
            "eligible_ai_picks": n_picks,
            "excluded": len(picks.exclusions) + len(quality.exclusions),
        },
        "quality": {
            "events": quality.events,
            "matched": quality.matched,
            "exact_matches": quality.exact_matches,
            "alias_matches": quality.alias_matches,
            "rejected": quality.rejected,
            "snapshots_accepted": quality.snapshots_accepted,
            "snapshots_rejected": quality.snapshots_rejected,
            "missing_timestamps": quality.missing_timestamps,
            "incomplete_markets": quality.incomplete_markets,
            "matches_without_prediction": quality.matches_without_prediction,
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
        "picks": pick_metrics,
        "baselines": {
            "naive_home": naive_metrics,
            "elo_no_value_filter": elo_metrics,
            "ai_picks_value": pick_metrics,
            "same_match_set": True,
            "match_set": "matched_matches_with_value_odds",
        },
        "bookmaker_descriptive": [
            {
                "match_id": row.match_id,
                "bookmaker": row.bookmaker,
                "available_at": row.available_at.isoformat(),
                "home_ev": row.home_ev,
                "draw_ev": row.draw_ev,
                "away_ev": row.away_ev,
                "selected": row.selected,
            }
            for row in descriptive_books
        ],
        "pit": {"passed": pit_ok, "rule": "available_at <= kickoff cutoff via OddsService"},
        "value_parity": {"passed": not parity_errors, "errors": parity_errors},
        "analyst": {
            "passed": analyst_ok,
            "provider": "deterministic-v0.1",
            "llm": False,
        },
        "candidate_promoted": False,
        "fingerprint": fingerprint,
        "findings": findings,
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
    }


def _settle_picks(items: list[Any], catalog: dict[str, CatalogMatch]) -> list[SettledBet]:
    bets: list[SettledBet] = []
    for item in items:
        match = catalog[item.match_id]
        bets.append(
            SettledBet(
                match_id=item.match_id,
                selection=item.selection,
                odds=float(item.odds),
                edge=float(item.edge),
                ev=float(item.ev),
                kickoff_at=item.kickoff_at,
                outcome=match.outcome,
                league=match.league,
                profit=settle_decimal(selection=item.selection, odds=float(item.odds), outcome=match.outcome),
                strategy="ai_picks_value",
            )
        )
    return bets


def _settle_argmax(
    matches: list[CatalogMatch],
    analyses: dict[str, FootballValueAnalysis],
    *,
    strategy: str,
) -> list[SettledBet]:
    bets: list[SettledBet] = []
    for match in matches:
        analysis = analyses[match.match_id]
        probs = {
            "HOME": analysis.prediction.home_probability,
            "DRAW": analysis.prediction.draw_probability,
            "AWAY": analysis.prediction.away_probability,
        }
        selection = max(probs, key=lambda name: (probs[name], name))
        odds = {
            "HOME": analysis.odds.home_odds,
            "DRAW": analysis.odds.draw_odds,
            "AWAY": analysis.odds.away_odds,
        }[selection]
        values = {
            "HOME": analysis.value.home,
            "DRAW": analysis.value.draw,
            "AWAY": analysis.value.away,
        }[selection]
        bets.append(
            SettledBet(
                match_id=match.match_id,
                selection=selection,
                odds=float(odds),
                edge=float(values.edge),
                ev=float(values.ev),
                kickoff_at=match.kickoff_at,
                outcome=match.outcome,
                league=match.league,
                profit=settle_decimal(selection=selection, odds=float(odds), outcome=match.outcome),
                strategy=strategy,
            )
        )
    return bets


def _settle_naive(
    matches: list[CatalogMatch],
    analyses: dict[str, FootballValueAnalysis],
    *,
    selection: str,
    strategy: str,
) -> list[SettledBet]:
    bets: list[SettledBet] = []
    for match in matches:
        analysis = analyses[match.match_id]
        odds = {
            "HOME": analysis.odds.home_odds,
            "DRAW": analysis.odds.draw_odds,
            "AWAY": analysis.odds.away_odds,
        }[selection]
        values = {
            "HOME": analysis.value.home,
            "DRAW": analysis.value.draw,
            "AWAY": analysis.value.away,
        }[selection]
        bets.append(
            SettledBet(
                match_id=match.match_id,
                selection=selection,
                odds=float(odds),
                edge=float(values.edge),
                ev=float(values.ev),
                kickoff_at=match.kickoff_at,
                outcome=match.outcome,
                league=match.league,
                profit=settle_decimal(selection=selection, odds=float(odds), outcome=match.outcome),
                strategy=strategy,
            )
        )
    return bets


def _bookmaker_descriptive(
    snapshots: tuple[OddsSnapshot, ...],
    analyses: dict[str, FootballValueAnalysis],
    matches: list[CatalogMatch],
) -> list[BookmakerDescriptiveRow]:
    rows: list[BookmakerDescriptiveRow] = []
    for match in matches:
        analysis = analyses[match.match_id]
        probs = {
            Football1x2Selection.HOME: Decimal(str(analysis.prediction.home_probability)),
            Football1x2Selection.DRAW: Decimal(str(analysis.prediction.draw_probability)),
            Football1x2Selection.AWAY: Decimal(str(analysis.prediction.away_probability)),
        }
        eligible = [
            item
            for item in snapshots
            if item.match_id == match.match_id
            and item.available_at <= match.kickoff_at
            and is_complete_football_1x2(item)
        ]
        for snapshot in eligible:
            prices = {item.selection: item.decimal_odds for item in snapshot.selections}
            rows.append(
                BookmakerDescriptiveRow(
                    match_id=match.match_id,
                    bookmaker=snapshot.bookmaker,
                    available_at=snapshot.available_at,
                    home_ev=float(expected_value(probs[Football1x2Selection.HOME], prices[Football1x2Selection.HOME])),
                    draw_ev=float(expected_value(probs[Football1x2Selection.DRAW], prices[Football1x2Selection.DRAW])),
                    away_ev=float(expected_value(probs[Football1x2Selection.AWAY], prices[Football1x2Selection.AWAY])),
                    selected=snapshot.bookmaker == analysis.odds.bookmaker
                    and snapshot.available_at == analysis.odds.available_at,
                )
            )
    return rows


def _findings(
    n_picks: int,
    pit_ok: bool,
    parity_ok: bool,
    analyst_ok: bool,
) -> dict[str, list[dict[str, str]]]:
    high: list[dict[str, str]] = []
    medium = [
        {
            "id": "M-01",
            "detail": (
                "Live Aug 21-24 historical odds were fetched dry-run and are not persisted; "
                "Value cannot be scored on that weekend."
            ),
        },
        {
            "id": "M-02",
            "detail": (
                "Fixture universe n is below the sufficiency threshold; "
                "results are descriptive, not a profitability proof."
            ),
        },
    ]
    low = [
        {
            "id": "L-01",
            "detail": "Last-complete bookmaker tie-break may retain a book other than Pinnacle.",
        },
        {
            "id": "L-02",
            "detail": "AI Picks V0.1 maximum_odds_age is 24h; a future closer-to-kickoff snapshot cadence is required.",
        },
    ]
    if not pit_ok or not parity_ok:
        high.append({"id": "H-01", "detail": "PIT or Value parity failed."})
    if not analyst_ok:
        medium.append({"id": "M-03", "detail": "Deterministic analyst could not consume Value context."})
    if n_picks < INSUFFICIENT_SAMPLE_N:
        medium.append({"id": "M-04", "detail": SAMPLE_WARNING})
    return {"high": high, "medium": medium, "low": low}


def _verdict(report: dict[str, Any]) -> str:
    if not report["pit"]["passed"] or not report["value_parity"]["passed"] or not report["reproducibility"]["passed"]:
        return "NO-GO"
    return "GO WITH CONDITIONS"


def run_live_weekend_model_pilot(*, dataset_path: Path, registry_dir: Path) -> dict[str, Any]:
    """Score football-elo-v1-candidate on the labeled weekend. Does not call The Odds API."""

    from predicta_ml.features.dataset import load_football_dataset

    dataset = load_football_dataset(dataset_path)
    frame = dataset.frame
    window = frame[
        (frame["event_at"] >= LIVE_WEEKEND_START)
        & (frame["event_at"] < LIVE_WEEKEND_END)
        & (frame["competition"].astype(str).isin(LIVE_COMPETITIONS))
    ]
    predictions_service = build_football_prediction_service(
        clock=Clock(LIVE_WEEKEND_CLOCK),
        registry_dir=registry_dir,
        dataset_path=dataset_path,
        model_version=CANDIDATE_MODEL_VERSION,
    )
    prior = frame[
        (frame["event_at"] < LIVE_WEEKEND_START) & (frame["competition"].astype(str).isin(LIVE_COMPETITIONS))
    ]
    freq_counts = prior["target"].astype(str).value_counts()
    freq_total = int(freq_counts.sum())
    frequency = {label: (int(freq_counts.get(label, 0)) / freq_total if freq_total else 0.0) for label in CLASS_LABELS}
    naive_label = max(CLASS_LABELS, key=lambda label: (frequency[label], label))

    rows: list[dict[str, Any]] = []
    elo_hits = 0
    freq_hits = 0
    home_hits = 0
    for _, raw in window.sort_values(["event_at", "match_id"]).iterrows():
        match_id = str(raw["match_id"])
        kickoff = raw["event_at"].to_pydatetime()
        outcome = str(raw["target"])
        identity_exclusion = WEEKEND_IDENTITY_EXCLUSIONS.get(match_id)
        prediction = predictions_service.predict(match_id, kickoff)
        probs = {
            "HOME": prediction.home_probability,
            "DRAW": prediction.draw_probability,
            "AWAY": prediction.away_probability,
        }
        elo_pick = max(probs, key=lambda name: (probs[name], name))
        if identity_exclusion is None:
            elo_hits += int(elo_pick == outcome)
            freq_hits += int(naive_label == outcome)
            home_hits += int(outcome == "HOME")
        rows.append(
            {
                "match_id": match_id,
                "kickoff_at": kickoff.isoformat(),
                "competition": str(raw["competition"]),
                "outcome": outcome,
                "elo_pick": elo_pick,
                "home_probability": prediction.home_probability,
                "draw_probability": prediction.draw_probability,
                "away_probability": prediction.away_probability,
                "identity_exclusion": identity_exclusion,
                "odds": None,
            }
        )
    matched_n = sum(1 for item in rows if item["identity_exclusion"] is None)
    return {
        "kind": "live_labeled_weekend",
        "model_version": CANDIDATE_MODEL_VERSION,
        "model_status": CANDIDATE_STATUS,
        "n_window": int(len(window.index)),
        "n_matched_identity": matched_n,
        "n_identity_excluded": len(WEEKEND_IDENTITY_EXCLUSIONS),
        "predictions": matched_n,
        "eligible_ai_picks": 0,
        "odds_persisted": False,
        "new_api_calls": 0,
        "new_credits": 0,
        "frequency_prior_n": freq_total,
        "frequency": frequency,
        "baselines": {
            "frequency": {"n": matched_n, "hit_rate": freq_hits / matched_n if matched_n else None},
            "naive_home": {"n": matched_n, "hit_rate": home_hits / matched_n if matched_n else None},
            "elo_no_value_filter": {"n": matched_n, "hit_rate": elo_hits / matched_n if matched_n else None},
            "ai_picks_value": {"n": 0, "hit_rate": None, "detail": "historical snapshots not persisted (dry-run)"},
        },
        "sample_warning": SAMPLE_WARNING,
        "rows": rows,
        "candidate_promoted": False,
    }
