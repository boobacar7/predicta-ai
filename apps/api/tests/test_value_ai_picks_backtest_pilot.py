from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from inspect import getsource

from app.ai_picks.config import AI_PICKS_VERSION, AiPicksThresholds
from app.ai_picks.service import AiPicksEngine
from app.backtesting.fixture_universe import (
    FIXTURE_CATALOG,
    HELIX_ID,
    RENNES_PSG_ID,
    STUB_PROBABILITIES,
    historical_odds_fixture_paths,
)
from app.backtesting.matching import classify_odds_event
from app.backtesting.odds_loader import inverted_psg_rennes_event, load_fixture_odds
from app.backtesting.pilot import (
    build_fixture_services,
    run_fixture_pilot,
    selected_snapshot_is_pit_safe,
    value_parity_errors,
)
from app.backtesting.types import CatalogMatch
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.exceptions import TemporalLeakageError
from app.predictions.features import InMemoryPitFeatureStore
from app.predictions.types import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS
from app.value_engine.calculator import VALUE_ENGINE_VERSION, expected_value
from predicta_ml.backtesting.value_metrics import INSUFFICIENT_SAMPLE_N, SAMPLE_WARNING
from predicta_ml.constants import CANDIDATE_STATUS as ML_STATUS
from tests.live_assets import CANDIDATE_ARTEFACT, PIT_DATASET, requires_live_assets


def test_fixture_pilot_is_reproducible_and_descriptive() -> None:
    report = run_fixture_pilot()
    assert report["kind"] == "descriptive_fixture"
    assert report["model_version"] == CANDIDATE_MODEL_VERSION
    assert report["model_status"] == CANDIDATE_STATUS
    assert report["value_engine_version"] == VALUE_ENGINE_VERSION
    assert report["ai_picks_version"] == AI_PICKS_VERSION
    assert report["candidate_promoted"] is False
    assert report["thresholds"]["optimized_on_test"] is False
    assert report["pit"]["passed"] is True
    assert report["value_parity"]["passed"] is True
    assert report["reproducibility"]["passed"] is True
    assert report["analyst"]["provider"] == "deterministic-v0.1"
    assert report["analyst"]["llm"] is False
    assert report["api_credits"]["new_api_calls"] == 0
    assert report["api_credits"]["new_credits"] == 0
    assert report["verdict"] == "GO WITH CONDITIONS"
    assert report["picks"]["n"] < INSUFFICIENT_SAMPLE_N
    assert report["sample_warning"] == SAMPLE_WARNING
    assert report["findings"]["high"] == []
    assert report["dataset"]["matched"] == 3
    assert report["dataset"]["rejected"] == 3
    assert report["dataset"]["eligible_ai_picks"] == 3
    assert report["picks"]["home"] == 1
    assert report["picks"]["draw"] == 1
    assert report["picks"]["away"] == 1
    assert report["baselines"]["same_match_set"] is True


def test_identity_rejects_isolated_paris_and_inverted_home_away() -> None:
    bundle = load_fixture_odds(
        historical_odds_fixture_paths(),
        FIXTURE_CATALOG,
        extra_events=[inverted_psg_rennes_event()],
    )
    statuses = {item.event_id: item.status for item in bundle.decisions}
    assert statuses["epl_helix_meridian_20260816"] == "exact"
    assert statuses["epl_bournemouth_brentford_20260816"] == "alias"
    assert statuses["fl1_marseille_monaco_20260816"] == "alias"
    assert statuses["epl_unknown_borough_20260816"] == "unmatched"
    assert statuses["fl1_paris_fc_angers_20260816"] == "isolated_team"
    assert statuses["fl1_psg_rennes_inverted_pilot"] == "inverted_home_away"
    assert all(item.match_id != RENNES_PSG_ID for item in bundle.snapshots)


def test_bookmaker_is_last_complete_not_best_ev() -> None:
    report = run_fixture_pilot()
    helix_books = [row for row in report["bookmaker_descriptive"] if row["match_id"] == HELIX_ID]
    selected = next(row for row in helix_books if row["selected"])
    assert selected["bookmaker"] == "betfair_ex_eu"
    pinnacle = next(row for row in helix_books if row["bookmaker"] == "pinnacle")
    assert pinnacle["selected"] is False
    assert "Pinnacle is not preferred" in report["bookmaker_policy"]


def test_post_cutoff_snapshot_is_not_selected() -> None:
    bundle = load_fixture_odds(historical_odds_fixture_paths(), FIXTURE_CATALOG, extra_events=[])
    services = build_fixture_services(bundle, FIXTURE_CATALOG)
    helix = next(item for item in FIXTURE_CATALOG if item.match_id == HELIX_ID)
    chosen = services.odds.market_at(match_id=HELIX_ID, market="1X2", cutoff_at=helix.kickoff_at)
    assert chosen.available_at < helix.kickoff_at
    later = [item for item in bundle.snapshots if item.match_id == HELIX_ID and item.available_at > helix.kickoff_at]
    assert later
    assert chosen.id not in {item.id for item in later}
    assert selected_snapshot_is_pit_safe(chosen.available_at, helix.kickoff_at)


def test_added_post_cutoff_odds_do_not_change_selection() -> None:
    bundle = load_fixture_odds(historical_odds_fixture_paths(), FIXTURE_CATALOG, extra_events=[])
    helix = next(item for item in FIXTURE_CATALOG if item.match_id == HELIX_ID)
    baseline = build_fixture_services(bundle, FIXTURE_CATALOG).odds.market_at(
        match_id=HELIX_ID, market="1X2", cutoff_at=helix.kickoff_at
    )
    leaked = OddsSnapshot(
        id="odd_leaked_after_kickoff",
        provider_id="leaked:pinnacle:1X2:2026-08-16T14:01:00+00:00",
        match_id=HELIX_ID,
        bookmaker="pinnacle",
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("9.99")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("9.99")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("9.99")),
        ),
        collected_at=helix.kickoff_at + timedelta(minutes=1),
        available_at=helix.kickoff_at + timedelta(minutes=1),
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
        raw_payload_id="raw_leaked",
    )
    poisoned = build_fixture_services(
        bundle.__class__(
            snapshots=bundle.snapshots + (leaked,),
            decisions=bundle.decisions,
            quality=bundle.quality,
        ),
        FIXTURE_CATALOG,
    )
    chosen = poisoned.odds.market_at(match_id=HELIX_ID, market="1X2", cutoff_at=helix.kickoff_at)
    assert chosen.id == baseline.id
    assert chosen.available_at == baseline.available_at
    analysis = poisoned.values.evaluate(HELIX_ID, helix.kickoff_at)
    assert analysis.odds.available_at == baseline.available_at
    assert analysis.odds.home_odds != 9.99


def test_future_result_does_not_change_pre_match_prediction_or_value() -> None:
    helix = next(item for item in FIXTURE_CATALOG if item.match_id == HELIX_ID)
    flipped = CatalogMatch(
        match_id=helix.match_id,
        home_team_id=helix.home_team_id,
        away_team_id=helix.away_team_id,
        home_team=helix.home_team,
        away_team=helix.away_team,
        league=helix.league,
        kickoff_at=helix.kickoff_at,
        outcome="AWAY",
        home_elo_pre=helix.home_elo_pre,
        away_elo_pre=helix.away_elo_pre,
    )
    catalog = (flipped,) + FIXTURE_CATALOG[1:]
    bundle = load_fixture_odds(historical_odds_fixture_paths(), catalog, extra_events=[])
    original = build_fixture_services(bundle, FIXTURE_CATALOG)
    mutated = build_fixture_services(bundle, catalog)
    first = original.predictions.predict(HELIX_ID, helix.kickoff_at)
    second = mutated.predictions.predict(HELIX_ID, helix.kickoff_at)
    assert first.home_probability == second.home_probability
    assert first.draw_probability == second.draw_probability
    assert first.away_probability == second.away_probability
    value_a = original.values.evaluate(HELIX_ID, helix.kickoff_at)
    value_b = mutated.values.evaluate(HELIX_ID, helix.kickoff_at)
    assert value_a.value.home.ev == value_b.value.home.ev
    assert value_a.odds.bookmaker == value_b.odds.bookmaker


def test_post_match_cutoff_is_refused_by_pit() -> None:
    helix = next(item for item in FIXTURE_CATALOG if item.match_id == HELIX_ID)
    store = InMemoryPitFeatureStore([helix.pit_features()])
    try:
        store.get_pit_features(HELIX_ID, helix.kickoff_at + timedelta(minutes=1))
    except TemporalLeakageError:
        return
    raise AssertionError("PIT must refuse a cutoff after kickoff.")


def test_inverted_event_does_not_bind_to_canonical_orientation() -> None:
    decision = classify_odds_event(inverted_psg_rennes_event(), FIXTURE_CATALOG)
    assert decision.status == "inverted_home_away"
    assert decision.match_id is None


def test_value_parity_matches_live_formulas() -> None:
    report = run_fixture_pilot()
    assert report["value_parity"]["errors"] == []
    bundle = load_fixture_odds(historical_odds_fixture_paths(), FIXTURE_CATALOG, extra_events=[])
    services = build_fixture_services(bundle, FIXTURE_CATALOG)
    helix = next(item for item in FIXTURE_CATALOG if item.match_id == HELIX_ID)
    analysis = services.values.evaluate(HELIX_ID, helix.kickoff_at)
    assert value_parity_errors(analysis) == []
    home, draw, away = STUB_PROBABILITIES[HELIX_ID]
    assert analysis.value.home.ev == float(
        expected_value(Decimal(str(home)), Decimal(str(analysis.odds.home_odds)))
    )
    assert analysis.value.draw.ev == float(
        expected_value(Decimal(str(draw)), Decimal(str(analysis.odds.draw_odds)))
    )
    assert analysis.value.away.ev == float(
        expected_value(Decimal(str(away)), Decimal(str(analysis.odds.away_odds)))
    )


def test_ai_picks_ranking_source_is_unchanged() -> None:
    source = getsource(AiPicksEngine._rank_opportunities)
    assert "-item.opportunity_score" in source
    assert "-item.ev" in source
    assert "-item.edge" in source
    assert AI_PICKS_VERSION == "ai-picks-0.1"
    assert VALUE_ENGINE_VERSION == "value-engine-0.1"
    report = run_fixture_pilot()
    ranks = report["fingerprint"]["picks"]
    assert [item[2] for item in ranks] == sorted(item[2] for item in ranks)
    assert CANDIDATE_MODEL_VERSION == "football-elo-v1-candidate"
    assert ML_STATUS == "candidate"


def test_ai_picks_uses_production_thresholds() -> None:
    thresholds = AiPicksThresholds()
    assert thresholds.minimum_edge == Decimal("0")
    assert thresholds.minimum_ev == Decimal("0")
    assert thresholds.minimum_model_probability == Decimal("0")
    assert thresholds.maximum_odds_age == timedelta(hours=24)


def test_quality_ledger_does_not_drop_rejections_silently() -> None:
    report = run_fixture_pilot()
    kinds = {item["kind"] for item in report["quality"]["exclusions"]}
    assert "isolated_team" in kinds
    assert "inverted_home_away" in kinds
    assert "unmatched_odds_event" in kinds
    assert report["quality"]["matches_without_odds"] >= 1
    assert report["ai_picks_exclusions"]


@requires_live_assets
def test_live_weekend_scores_candidate_without_new_odds_calls() -> None:
    from app.backtesting.pilot import run_live_weekend_model_pilot

    report = run_live_weekend_model_pilot(
        dataset_path=PIT_DATASET,
        registry_dir=CANDIDATE_ARTEFACT.parent.parent,
    )
    assert report["model_version"] == CANDIDATE_MODEL_VERSION
    assert report["candidate_promoted"] is False
    assert report["new_api_calls"] == 0
    assert report["new_credits"] == 0
    assert report["odds_persisted"] is False
    assert report["eligible_ai_picks"] == 0
    assert report["n_matched_identity"] == 17
    assert report["n_identity_excluded"] == 2
    assert report["predictions"] == 17
    elo = report["baselines"]["elo_no_value_filter"]
    assert elo["n"] == 17
    assert elo["hit_rate"] is not None
    assert report["baselines"]["ai_picks_value"]["n"] == 0
