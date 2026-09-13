from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import getsource

from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.ai_picks.models import ExclusionReason
from app.ai_picks.service import AiPicksEngine
from app.backtesting.matching import classify_odds_event
from app.backtesting.odds_loader import inverted_psg_rennes_event
from app.backtesting.persisted import (
    api_snapshot_from_ingestion,
    build_persisted_services,
    run_persisted_weekend_pilot,
)
from app.backtesting.pilot import (
    WEEKEND_IDENTITY_EXCLUSIONS,
    StubCandidatePredictor,
    selected_snapshot_is_pit_safe,
    value_parity_errors,
)
from app.backtesting.types import CatalogMatch
from app.core.clock import Clock
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.exceptions import TemporalLeakageError
from app.predictions.features import InMemoryPitFeatureStore
from app.predictions.service import FootballPredictionService
from app.predictions.types import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS
from app.value_engine.calculator import VALUE_ENGINE_VERSION, expected_value, implied_probability

HELIX_ID = "mth_football-sportmonks-helix-persist"
PARIS_ID = "mth_football-sportmonks-19715629"
RENNES_ID = "mth_football-sportmonks-19715631"
KICKOFF = datetime(2026, 8, 21, 19, tzinfo=UTC)
NEAR = datetime(2026, 8, 21, 18, 49, tzinfo=UTC)
STALE = datetime(2026, 8, 20, 12, tzinfo=UTC)
AFTER = datetime(2026, 8, 21, 19, 5, tzinfo=UTC)

CATALOG = (
    CatalogMatch(
        match_id=HELIX_ID,
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_team="Helix FC",
        away_team="Meridian Athletic",
        league="Premier League",
        kickoff_at=KICKOFF,
        outcome="HOME",
        home_elo_pre=1680.0,
        away_elo_pre=1500.0,
    ),
    CatalogMatch(
        match_id=PARIS_ID,
        home_team_id="tm_troyes",
        away_team_id="tm_paris",
        home_team="Troyes",
        away_team="Paris",
        league="Ligue 1",
        kickoff_at=datetime(2026, 8, 22, 18, 45, tzinfo=UTC),
        outcome="DRAW",
        home_elo_pre=1500.0,
        away_elo_pre=1500.0,
    ),
    CatalogMatch(
        match_id=RENNES_ID,
        home_team_id="tm_rennes",
        away_team_id="tm_psg",
        home_team="Rennes",
        away_team="Paris Saint Germain",
        league="Ligue 1",
        kickoff_at=datetime(2026, 8, 23, 18, 45, tzinfo=UTC),
        outcome="HOME",
        home_elo_pre=1550.0,
        away_elo_pre=1850.0,
    ),
)

PROBS = {
    HELIX_ID: (0.60, 0.20, 0.20),
    PARIS_ID: (0.34, 0.33, 0.33),
    RENNES_ID: (0.22, 0.24, 0.54),
}


def _snapshot(
    *,
    snapshot_id: str,
    available_at: datetime,
    odds: tuple[str, str, str] = ("1.80", "3.70", "4.40"),
    match_id: str = HELIX_ID,
) -> OddsSnapshot:
    return OddsSnapshot(
        id=snapshot_id,
        provider_id=f"{snapshot_id}:pinnacle:1X2:{available_at.isoformat()}",
        match_id=match_id,
        bookmaker="pinnacle",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal(odds[0])),
            OddsSelection(Football1x2Selection.DRAW, Decimal(odds[1])),
            OddsSelection(Football1x2Selection.AWAY, Decimal(odds[2])),
        ),
        collected_at=available_at,
        available_at=available_at,
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
        raw_payload_id="raw_persist_pilot",
    )


def _predictor() -> FootballPredictionService:
    return FootballPredictionService(
        clock=Clock(KICKOFF),
        features=InMemoryPitFeatureStore([item.pit_features() for item in CATALOG]),
        model=StubCandidatePredictor(PROBS),
    )


def test_persisted_weekend_scores_value_and_ai_picks_without_tuning() -> None:
    snapshots = (_snapshot(snapshot_id="odd_helix_near", available_at=NEAR),)
    report = run_persisted_weekend_pilot(
        catalog=CATALOG,
        snapshots=snapshots,
        predictions=_predictor(),
    )
    assert report["kind"] == "persisted_live_weekend"
    assert report["model_version"] == CANDIDATE_MODEL_VERSION
    assert report["model_status"] == CANDIDATE_STATUS
    assert report["value_engine_version"] == VALUE_ENGINE_VERSION
    assert report["ai_picks_version"] == AI_PICKS_VERSION
    assert report["candidate_promoted"] is False
    assert report["thresholds"]["optimized_on_test"] is False
    assert report["pit"]["passed"] is True
    assert report["value_parity"]["passed"] is True
    assert report["ai_picks_parity"]["passed"] is True
    assert report["reproducibility"]["passed"] is True
    assert report["dataset"]["identity_matched"] == 1
    assert report["dataset"]["identity_rejected"] == 2
    assert report["dataset"]["matches_with_odds"] == 1
    assert report["dataset"]["eligible_ai_picks"] >= 1
    assert report["model_performance"]["n"] == 1
    assert "Not a betting ROI" in report["model_performance"]["note"]
    kinds = {item["kind"] for item in report["quality"]["exclusions"]}
    assert "isolated_team" in kinds
    assert "inverted_home_away" in kinds
    assert PARIS_ID in WEEKEND_IDENTITY_EXCLUSIONS
    assert RENNES_ID in WEEKEND_IDENTITY_EXCLUSIONS
    pick_ids = {item[0] for item in report["fingerprint"]["picks"]}
    assert PARIS_ID not in pick_ids
    assert RENNES_ID not in pick_ids


def test_stale_odds_are_excluded_not_threshold_changes() -> None:
    snapshots = (_snapshot(snapshot_id="odd_helix_stale", available_at=STALE),)
    report = run_persisted_weekend_pilot(
        catalog=(CATALOG[0],),
        snapshots=snapshots,
        predictions=_predictor(),
    )
    reasons = {item["reason"] for item in report["ai_picks_exclusions"]}
    assert "stale_odds" in reasons
    assert report["thresholds"]["maximum_odds_age_seconds"] == 24 * 3600
    assert AiPicksThresholds().maximum_odds_age == timedelta(hours=24)


def test_post_kickoff_snapshot_is_not_selected() -> None:
    before = _snapshot(snapshot_id="odd_helix_before", available_at=NEAR)
    leaked = _snapshot(snapshot_id="odd_helix_after", available_at=AFTER, odds=("9.99", "9.99", "9.99"))
    services = build_persisted_services((CATALOG[0],), (before, leaked), predictions=_predictor())
    chosen = services.odds.market_at(match_id=HELIX_ID, market="1X2", cutoff_at=KICKOFF)
    assert chosen.id == before.id
    assert selected_snapshot_is_pit_safe(chosen.available_at, KICKOFF)
    analysis = services.values.evaluate(HELIX_ID, KICKOFF)
    assert analysis.odds.home_odds != 9.99
    assert value_parity_errors(analysis) == []


def test_cutoff_after_kickoff_is_refused() -> None:
    store = InMemoryPitFeatureStore([CATALOG[0].pit_features()])
    try:
        store.get_pit_features(HELIX_ID, KICKOFF + timedelta(minutes=1))
    except TemporalLeakageError:
        return
    raise AssertionError("PIT must refuse a cutoff after kickoff.")


def test_known_identity_exclusions_never_become_ai_picks() -> None:
    rennes_kickoff = CATALOG[2].kickoff_at
    rennes_odds = _snapshot(
        snapshot_id="odd_rennes_near",
        available_at=rennes_kickoff - timedelta(minutes=10),
        match_id=RENNES_ID,
    )
    report = run_persisted_weekend_pilot(
        catalog=CATALOG,
        snapshots=(
            _snapshot(snapshot_id="odd_helix_near", available_at=NEAR),
            rennes_odds,
        ),
        predictions=_predictor(),
    )
    pick_ids = {item[0] for item in report["fingerprint"]["picks"]}
    assert RENNES_ID not in pick_ids
    assert PARIS_ID not in pick_ids
    kinds = {item["kind"] for item in report["quality"]["exclusions"]}
    assert "inverted_home_away" in kinds
    assert "isolated_team" in kinds


def test_inverted_and_isolated_events_stay_rejected() -> None:
    decision = classify_odds_event(inverted_psg_rennes_event(), CATALOG)
    assert decision.status == "inverted_home_away"
    assert decision.match_id is None
    paris_event = {
        "id": "fl1_troyes_paris_fc",
        "commence_time": "2026-08-22T18:45:00Z",
        "home_team": "Troyes",
        "away_team": "Paris FC",
    }
    isolated = classify_odds_event(paris_event, CATALOG)
    assert isolated.status == "isolated_team"
    assert isolated.match_id is None


def test_value_formulas_and_ai_picks_ranking_are_unchanged() -> None:
    snapshots = (_snapshot(snapshot_id="odd_helix_near", available_at=NEAR),)
    report = run_persisted_weekend_pilot(
        catalog=(CATALOG[0],),
        snapshots=snapshots,
        predictions=_predictor(),
    )
    analysis_errors = report["value_parity"]["errors"]
    assert analysis_errors == []
    home = Decimal("0.60")
    implied = implied_probability(Decimal("1.80"))
    assert abs(Decimal(str(report["rows"][0]["home_implied"])) - implied) < Decimal("0.000000001")
    assert report["rows"][0]["home_ev"] == float(expected_value(home, Decimal("1.80")))
    source = getsource(AiPicksEngine._rank_opportunities)
    assert "-item.opportunity_score" in source
    assert AI_PICKS_VERSION == "ai-picks-0.1"
    assert ExclusionReason.STALE_ODDS.value == "stale_odds"


def test_api_snapshot_conversion_keeps_provenance() -> None:
    class _Sel:
        def __init__(self, selection: str, price: str) -> None:
            self.selection = selection
            self.decimal_odds = Decimal(price)

    class _Prov:
        provider_id = "evt:pinnacle:1X2:2026-08-21T18:49:00+00:00"
        collected_at = NEAR
        available_at = NEAR
        source = LIVE_ODDS_SOURCE
        data_mode = "live"
        raw_payload_id = "raw_canonical"

    class _Snap:
        id = "odd_canonical"
        match_id = HELIX_ID
        bookmaker = "pinnacle"
        market = "1X2"
        selections = (
            _Sel("HOME", "1.80"),
            _Sel("DRAW", "3.70"),
            _Sel("AWAY", "4.40"),
        )
        provenance = _Prov()

    mapped = api_snapshot_from_ingestion(_Snap())
    assert mapped.raw_payload_id == "raw_canonical"
    assert mapped.available_at == NEAR
    assert mapped.source == LIVE_ODDS_SOURCE
    assert mapped.data_mode == "live"
