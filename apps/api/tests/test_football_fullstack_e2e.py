"""Reproducible Lincoln full-stack football E2E.

Bare clones skip when gitignored PIT parquet / candidate artefact / raw archive
are absent. Locally, with ``var/`` present, the real ``football-elo-v1-candidate``
artefact is loaded. The model is never mocked.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
import yaml
from app.ai_analyst.context import (
    AnalystContext,
    AnalystIdentity,
    AnalystPrediction,
    highest_ev_selection,
    value_for_selection,
)
from app.ai_analyst.rendering import render_analyst_summary
from app.core.clock import parse_rfc3339
from app.match_identity.models import MatchIdentity
from app.odds.exceptions import OddsUnavailableError
from app.odds.providers import MOCK_ODDS_SOURCE, LiveOddsProvider, MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection
from app.predictions.simplex import renormalize_1x2
from app.predictions.types import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS, ELO_FEATURES
from app.schemas import FootballModelPrediction
from app.value_engine.calculator import (
    VALUE_ENGINE_VERSION,
    edge,
    expected_value,
    implied_probability,
    no_vig_probabilities,
    overround,
)
from app.value_engine.models import FootballValueAnalysis
from fastapi.testclient import TestClient
from httpx import Response
from jsonschema import Draft202012Validator
from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.registry.artifact import load_registry
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from tests.conftest import make_app, make_client
from tests.live_assets import (
    CANDIDATE_ARTEFACT,
    PIT_DATASET,
    RAW_ARCHIVE,
    football_http_stack_available,
    requires_football_http,
    requires_live_assets,
    requires_pit_dataset,
)
from tests.test_ai_analyst_llm import _payload, _scripted
from tests.test_ai_analyst_narrative_invariant import MALICIOUS_NARRATIVES

MATCH_ID = "mth_football-sportmonks-19719892"
HOME_TEAM = "Lincoln Red Imps"
AWAY_TEAM = "Inter Club d'Escaldes"
LEAGUE = "Champions League"
KICKOFF = "2026-07-07T16:00:00Z"
KICKOFF_DT = datetime(2026, 7, 7, 16, tzinfo=UTC)
HOME_TEAM_ID = "tm_football-sportmonks-10068"
AWAY_TEAM_ID = "tm_football-sportmonks-17303"
REPO = Path(__file__).resolve().parents[3]
CONTRACT = REPO / "contracts" / "openapi.yaml"
FEATURES_SOURCE = Path(__file__).resolve().parents[1] / "app" / "predictions" / "features.py"
ROUTER_SOURCE = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "router.py"
LLM_PROVIDER_SOURCE = Path(__file__).resolve().parents[1] / "app" / "ai_analyst" / "llm_provider.py"
SELECTIONS = (
    Football1x2Selection.HOME,
    Football1x2Selection.DRAW,
    Football1x2Selection.AWAY,
)
PROBABILITY_KEYS = ("home_probability", "draw_probability", "away_probability")
FORBIDDEN = ("guaranteed", "safe bet", "sure win", "certain", "pari sûr", "gain garanti")
BARE_CLONE_SKIP = (
    "gitignored PIT parquet / football-elo-v1-candidate artefact / raw archive are absent; "
    "CI does not download live sports data"
)


def _validate(schema_name: str, payload: dict) -> None:
    spec = yaml.safe_load(CONTRACT.read_text())
    document = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://predicta.local/openapi.yaml",
        "components": spec["components"],
    }
    resource = Resource.from_contents(document, default_specification=DRAFT202012)
    registry = Registry().with_resource(document["$id"], resource)
    schema = {"$ref": f"{document['$id']}#/components/schemas/{schema_name}"}
    Draft202012Validator(schema, registry=registry).validate(payload)


def _assert_problem(response: Response, *, status: int, type_uri: str) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == type_uri
    assert body["status"] == status
    assert body["title"]
    assert body["detail"]
    assert body["request_id"]
    assert "data" not in body
    assert response.headers["X-Request-ID"] == body["request_id"]
    _validate("ProblemDetails", body)
    return body


def _selection_map(home: object, draw: object, away: object) -> dict[Football1x2Selection, Decimal]:
    return {
        Football1x2Selection.HOME: Decimal(str(home)),
        Football1x2Selection.DRAW: Decimal(str(draw)),
        Football1x2Selection.AWAY: Decimal(str(away)),
    }


def _context_from_http(identity: dict, prediction: dict, value: dict) -> AnalystContext:
    analysis = FootballValueAnalysis.model_validate(value)
    pred = FootballModelPrediction.model_validate(prediction)
    analyst_prediction = AnalystPrediction(
        home_probability=Decimal(str(pred.home_probability)),
        draw_probability=Decimal(str(pred.draw_probability)),
        away_probability=Decimal(str(pred.away_probability)),
        model_version=pred.model_version,
        model_status=pred.model_status,
        dataset_version=pred.dataset_version,
        cutoff_at=pred.cutoff_at,
    )
    favorite = analyst_prediction.favorite_selection()
    kickoff = identity["kickoff_at"]
    if isinstance(kickoff, str):
        kickoff = parse_rfc3339(kickoff)
    return AnalystContext(
        identity=AnalystIdentity(
            match_id=identity["match_id"],
            home_team=identity["home_team"],
            away_team=identity["away_team"],
            league=identity["league"],
            kickoff_at=kickoff,
        ),
        prediction=analyst_prediction,
        value=value_for_selection(analysis, favorite),
        generated_at=pred.generated_at,
        data_mode="mock",
        value_selection=highest_ev_selection(analysis),
    )


def _valid_claims(context: AnalystContext) -> list[dict[str, object]]:
    assert context.value is not None
    return [
        {
            "claim_type": "model_favorite",
            "subject": "HOME",
            "evidence_ids": ["prediction.model_favorite"],
        },
        {
            "claim_type": "model_probability",
            "subject": "HOME",
            "value": float(context.prediction.home_probability),
            "evidence_ids": ["prediction.home_probability"],
        },
        {
            "claim_type": "value_selection",
            "subject": "AWAY",
            "evidence_ids": ["value.value_selection"],
        },
        {
            "claim_type": "ev",
            "subject": "HOME",
            "value": float(context.value.ev),
            "evidence_ids": ["value.ev"],
        },
        {
            "claim_type": "data_mode",
            "value": "mock",
            "evidence_ids": ["metadata.data_mode"],
        },
    ]


def test_bare_clone_skip_is_explicit_when_runtime_artefacts_are_absent() -> None:
    if not football_http_stack_available():
        pytest.skip(BARE_CLONE_SKIP)
    assert PIT_DATASET.is_file()
    assert CANDIDATE_ARTEFACT.is_file()
    assert RAW_ARCHIVE.is_dir()
    assert any(RAW_ARCHIVE.rglob("*.json"))


@requires_football_http
def test_lincoln_layers_share_one_business_truth() -> None:
    client = make_client()
    identity_response = client.get(f"/api/v1/matches/{MATCH_ID}", headers={"X-Request-ID": "req_e2e_id"})
    prediction_response = client.get(
        f"/api/v1/football/predictions/{MATCH_ID}",
        headers={"X-Request-ID": "req_e2e_pred"},
    )
    value_response = client.get(f"/api/v1/football/value/{MATCH_ID}", headers={"X-Request-ID": "req_e2e_value"})
    picks_response = client.get("/api/v1/football/ai-picks", headers={"X-Request-ID": "req_e2e_picks"})
    analyst_response = client.get(
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
        headers={"X-Request-ID": "req_e2e_analyst"},
    )
    for response, request_id in (
        (identity_response, "req_e2e_id"),
        (prediction_response, "req_e2e_pred"),
        (value_response, "req_e2e_value"),
        (picks_response, "req_e2e_picks"),
        (analyst_response, "req_e2e_analyst"),
    ):
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == request_id
        assert response.json()["request_id"] == request_id

    identity = identity_response.json()
    prediction = prediction_response.json()
    value = value_response.json()
    picks = picks_response.json()
    analyst = analyst_response.json()
    _validate("MatchDetailEnvelope", identity)
    _validate("FootballModelPredictionEnvelope", prediction)
    _validate("FootballValueAnalysisEnvelope", value)
    _validate("AiPicksEnvelope", picks)
    _validate("FootballAiAnalystEnvelope", analyst)

    identity_data = identity["data"]
    prediction_data = prediction["data"]
    value_data = value["data"]
    picks_data = picks["data"]
    analyst_data = analyst["data"]

    for payload in (identity_data, prediction_data, value_data, analyst_data):
        assert payload["match_id"] == MATCH_ID
    assert all(item["match_id"] == MATCH_ID for item in picks_data["items"])
    assert identity_data["home_team"] == HOME_TEAM
    assert identity_data["away_team"] == AWAY_TEAM
    assert identity_data["league"] == LEAGUE
    assert identity_data["kickoff_at"] == KICKOFF
    assert identity_data["home_team_id"] == HOME_TEAM_ID
    assert identity_data["away_team_id"] == AWAY_TEAM_ID
    assert identity_data["resource_scope"] == "structural_identity"
    assert identity_data["data_mode"] == "live"
    for item in picks_data["items"]:
        assert item["home_team"] == HOME_TEAM
        assert item["away_team"] == AWAY_TEAM
        assert item["league"] == LEAGUE
        assert item["kickoff_at"] == KICKOFF
    assert analyst_data["home_team"] == HOME_TEAM
    assert analyst_data["away_team"] == AWAY_TEAM
    assert analyst_data["league"] == LEAGUE
    assert analyst_data["kickoff_at"] == KICKOFF

    frame = load_football_dataset(PIT_DATASET).frame
    pit_row = frame.loc[frame["match_id"] == MATCH_ID].iloc[0]
    pit_data_mode = str(pit_row["data_mode"])
    assert pit_data_mode == "live"
    assert prediction["data_mode"] == pit_data_mode
    assert prediction_data["model_version"] == CANDIDATE_MODEL_VERSION
    assert prediction_data["model_status"] == CANDIDATE_STATUS
    assert prediction_data["model_status"] != "champion"
    assert prediction_data["cutoff_policy"] == "pre_kickoff"
    assert prediction_data["cutoff_at"] == KICKOFF
    assert prediction_data["dataset_version"] == "football-1x2-history-0.3"
    assert prediction_data["feature_schema_version"] == "football-1x2-features-0.3"
    total = sum(prediction_data[key] for key in PROBABILITY_KEYS)
    assert total == pytest.approx(1.0, abs=1e-9)
    for key in PROBABILITY_KEYS:
        assert 0.0 < prediction_data[key] < 1.0
    assert "expected_value" not in prediction_data
    assert "home_score" not in prediction_data
    assert "result" not in prediction_data

    artefact = load_registry(CANDIDATE_ARTEFACT)
    diffs = np.array([float(pit_row["elo_diff"])], dtype=np.float64)
    raw = np.asarray(artefact["predictors"]["elo"].predict_diffs(diffs), dtype=np.float64)
    calibrated = np.asarray(artefact["calibrators"]["elo"].transform(raw), dtype=np.float64)
    expected = renormalize_1x2(float(calibrated[0][0]), float(calibrated[0][1]), float(calibrated[0][2])).as_tuple()
    api = (
        prediction_data["home_probability"],
        prediction_data["draw_probability"],
        prediction_data["away_probability"],
    )
    assert api == expected
    assert ELO_FEATURES == ("home_elo_pre", "away_elo_pre", "elo_diff")
    features_source = FEATURES_SOURCE.read_text(encoding="utf-8")
    assert 'row["home_elo_pre"]' in features_source
    assert "home_score" not in features_source
    assert "away_score" not in features_source
    assert '"target"' not in features_source
    identity_fields = set(MatchIdentity.__dataclass_fields__)
    assert identity_fields.isdisjoint({"status", "home_score", "away_score", "result", "events"})

    assert value["data_mode"] == "mock"
    metadata = value_data["metadata"]
    assert metadata["value_engine_version"] == VALUE_ENGINE_VERSION
    assert metadata["model_version"] == CANDIDATE_MODEL_VERSION
    assert metadata["model_status"] == CANDIDATE_STATUS
    assert metadata["odds_source"] == MOCK_ODDS_SOURCE
    assert metadata["data_mode"] == "mock"
    assert metadata["cutoff_at"] == KICKOFF
    assert value_data["odds"]["available_at"] == "2026-07-07T15:00:00Z"
    assert parse_rfc3339(value_data["odds"]["available_at"]) < KICKOFF_DT
    assert parse_rfc3339(value_data["odds"]["collected_at"]) < parse_rfc3339(value_data["odds"]["available_at"])
    assert value_data["prediction"] == {
        "home_probability": prediction_data["home_probability"],
        "draw_probability": prediction_data["draw_probability"],
        "away_probability": prediction_data["away_probability"],
    }

    odds = _selection_map(
        value_data["odds"]["home_odds"],
        value_data["odds"]["draw_odds"],
        value_data["odds"]["away_odds"],
    )
    model_probabilities = _selection_map(
        prediction_data["home_probability"],
        prediction_data["draw_probability"],
        prediction_data["away_probability"],
    )
    implied = {selection: implied_probability(price) for selection, price in odds.items()}
    market_overround = overround(tuple(odds.values()))
    no_vig, returned_overround = no_vig_probabilities(odds)
    assert returned_overround == market_overround
    assert market_overround == sum(implied.values(), Decimal(0))
    assert value_data["market_probabilities"]["overround"] == pytest.approx(float(market_overround))
    published_markets = {
        Football1x2Selection.HOME: value_data["market_probabilities"]["home"],
        Football1x2Selection.DRAW: value_data["market_probabilities"]["draw"],
        Football1x2Selection.AWAY: value_data["market_probabilities"]["away"],
    }
    published_values = {
        Football1x2Selection.HOME: value_data["value"]["home"],
        Football1x2Selection.DRAW: value_data["value"]["draw"],
        Football1x2Selection.AWAY: value_data["value"]["away"],
    }
    for selection in SELECTIONS:
        assert published_markets[selection]["implied_probability"] == pytest.approx(float(implied[selection]))
        assert published_markets[selection]["no_vig_probability"] == pytest.approx(float(no_vig[selection]))
        expected_edge = edge(model_probabilities[selection], implied[selection])
        expected_ev = expected_value(model_probabilities[selection], odds[selection])
        assert published_values[selection]["edge"] == pytest.approx(float(expected_edge))
        assert published_values[selection]["ev"] == pytest.approx(float(expected_ev))

    assert picks["data_mode"] == "mock"
    assert picks_data["metadata"]["ai_picks_version"] == "ai-picks-0.1"
    assert picks_data["metadata"]["scoring_formula"] == "opportunity_score = EV + Edge"
    assert picks_data["items"]
    ranks = [item["rank"] for item in picks_data["items"]]
    assert ranks == list(range(1, len(ranks) + 1))
    scores = [item["opportunity_score"] for item in picks_data["items"]]
    assert scores == sorted(scores, reverse=True)
    for item in picks_data["items"]:
        assert item["model_version"] == CANDIDATE_MODEL_VERSION
        assert item["model_status"] == CANDIDATE_STATUS
        assert item["value_engine_version"] == VALUE_ENGINE_VERSION
        assert item["ai_picks_version"] == "ai-picks-0.1"
        assert item["odds_source"] == MOCK_ODDS_SOURCE
        assert item["data_mode"] == "mock"
        assert item["cutoff_at"] == KICKOFF
        selection = Football1x2Selection(item["selection"])
        assert item["model_probability"] == pytest.approx(float(model_probabilities[selection]))
        assert item["odds"] == pytest.approx(float(odds[selection]))
        assert item["implied_probability"] == pytest.approx(float(implied[selection]))
        assert item["no_vig_probability"] == pytest.approx(float(no_vig[selection]))
        assert item["edge"] == pytest.approx(float(published_values[selection]["edge"]))
        assert item["ev"] == pytest.approx(float(published_values[selection]["ev"]))
        assert item["opportunity_score"] == pytest.approx(item["ev"] + item["edge"])
    best = picks_data["items"][0]
    assert best["rank"] == 1
    assert best["selection"] == "AWAY"
    excluded_home = [item for item in picks_data["exclusions"] if item.get("selection") == "HOME"]
    assert excluded_home
    assert excluded_home[0]["reason"] in {"negative_ev", "negative_edge"}

    assert analyst["data_mode"] == "mock"
    assert analyst_data["model_favorite"] == "HOME"
    assert analyst_data["value"]["selection"] == "HOME"
    assert analyst_data["value"]["value_selection"] == "AWAY"
    assert analyst_data["model_favorite"] != analyst_data["value"]["value_selection"]
    assert analyst_data["prediction"]["model_version"] == CANDIDATE_MODEL_VERSION
    assert analyst_data["prediction"]["model_status"] == CANDIDATE_STATUS
    assert analyst_data["prediction"]["cutoff_at"] == KICKOFF
    assert analyst_data["prediction"]["home_probability"] == prediction_data["home_probability"]
    assert analyst_data["prediction"]["draw_probability"] == prediction_data["draw_probability"]
    assert analyst_data["prediction"]["away_probability"] == prediction_data["away_probability"]
    assert analyst_data["value"]["value_engine_version"] == VALUE_ENGINE_VERSION
    assert analyst_data["value"]["odds"] == pytest.approx(float(odds[Football1x2Selection.HOME]))
    assert analyst_data["value"]["ev"] == pytest.approx(float(published_values[Football1x2Selection.HOME]["ev"]))
    assert analyst_data["value"]["edge"] == pytest.approx(float(published_values[Football1x2Selection.HOME]["edge"]))
    assert analyst_data["analyst"]["analysis_version"] == "ai-analyst-0.1"
    assert analyst_data["analyst"]["data_quality"]["data_mode"] == "mock"
    assert analyst_data["analyst"]["data_quality"]["model_status"] == CANDIDATE_STATUS
    serialized = " ".join(response.text.casefold() for response in (picks_response, analyst_response))
    assert not any(term in serialized for term in FORBIDDEN)


@requires_live_assets
def test_lincoln_prediction_live_and_odds_mock_remain_distinguishable() -> None:
    client = make_client()
    prediction = client.get(f"/api/v1/football/predictions/{MATCH_ID}").json()
    value = client.get(f"/api/v1/football/value/{MATCH_ID}").json()
    assert prediction["data_mode"] == "live"
    assert value["data_mode"] == "mock"
    assert value["data"]["metadata"]["data_mode"] == "mock"
    assert value["data"]["metadata"]["odds_source"] == MOCK_ODDS_SOURCE
    assert prediction["data_mode"] != value["data_mode"]
    router = ROUTER_SOURCE.read_text(encoding="utf-8")
    assert 'data_mode="live"' not in router
    assert "data_mode='live'" not in router
    live = LiveOddsProvider()
    with pytest.raises(OddsUnavailableError, match="never synthesized"):
        live.fetch(MATCH_ID, "1X2")
    assert MockOddsProvider().data_mode == "mock"
    assert live.data_mode == "live"


@requires_football_http
def test_lincoln_temporal_safety_and_missing_snapshot() -> None:
    client = make_client()
    endpoints = (
        f"/api/v1/football/predictions/{MATCH_ID}",
        f"/api/v1/football/value/{MATCH_ID}",
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
    )
    for path in endpoints:
        exact = client.get(path, params={"cutoff_at": KICKOFF}, headers={"X-Request-ID": "req_e2e_exact"})
        assert exact.status_code == 200
        _assert_problem(
            client.get(path, params={"cutoff_at": "2026-07-07T15:59:59Z"}, headers={"X-Request-ID": "req_e2e_early"}),
            status=422,
            type_uri="/problems/pit-features-unavailable",
        )
        _assert_problem(
            client.get(path, params={"cutoff_at": "2026-07-07T16:00:01Z"}, headers={"X-Request-ID": "req_e2e_late"}),
            status=409,
            type_uri="/problems/temporal-leakage",
        )
    app = make_app()
    app.state.container.football_odds = OddsService(
        provider=MockOddsProvider(()),
        repository=InMemoryOddsRepository(),
    )
    isolated = TestClient(app)
    _assert_problem(
        isolated.get(f"/api/v1/football/value/{MATCH_ID}", headers={"X-Request-ID": "req_e2e_no_odds"}),
        status=422,
        type_uri="/problems/odds-unavailable",
    )


@requires_pit_dataset
def test_http_errors_do_not_fallback_to_mock(tmp_path: Path) -> None:
    client = make_client(football_registry_dir=tmp_path)
    for path in (
        f"/api/v1/football/predictions/{MATCH_ID}",
        f"/api/v1/football/value/{MATCH_ID}",
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
    ):
        body = _assert_problem(
            client.get(path, headers={"X-Request-ID": "req_e2e_artefact"}),
            status=503,
            type_uri="/problems/model-artefact-not-found",
        )
        assert "data_mode" not in body
        assert HOME_TEAM not in str(body)
    unknown = make_client().get(
        "/api/v1/matches/mth_football-sportmonks-unknown",
        headers={"X-Request-ID": "req_e2e_404"},
    )
    _assert_problem(unknown, status=404, type_uri="/problems/not-found")
    assert HOME_TEAM not in unknown.text


@requires_football_http
def test_same_claims_malicious_narratives_yield_identical_lincoln_summary() -> None:
    client = make_client()
    identity = client.get(f"/api/v1/matches/{MATCH_ID}").json()["data"]
    prediction = client.get(f"/api/v1/football/predictions/{MATCH_ID}").json()["data"]
    value = client.get(f"/api/v1/football/value/{MATCH_ID}").json()["data"]
    http_report = client.get(f"/api/v1/football/ai-analyst/{MATCH_ID}").json()["data"]
    context = _context_from_http(identity, prediction, value)
    claims = _valid_claims(context)
    baseline = _scripted(_payload(narrative="Lorem ipsum.", claims=claims)).generate_analysis(context)
    expected = baseline.model_dump(mode="json")
    assert baseline.provider == "llm-v0.1"
    assert "Lorem ipsum." not in baseline.summary
    assert http_report["model_favorite"] == "HOME"
    assert http_report["value"]["value_selection"] == "AWAY"
    variants = ("HOME is strongest.", "AWAY is strongest.", "PSG is guaranteed to win.", *MALICIOUS_NARRATIVES[:80])
    assert len(variants) >= 80
    for narrative in variants:
        explanation = _scripted(_payload(narrative=narrative, claims=claims)).generate_analysis(context)
        assert explanation.model_dump(mode="json") == expected, narrative
        assert narrative.casefold() not in explanation.summary.casefold()
    params = inspect.signature(render_analyst_summary).parameters
    assert "narrative" not in params
    assert "text" not in params
    assert "UNTRUSTED LLM TEXT" in LLM_PROVIDER_SOURCE.read_text(encoding="utf-8")
    llm_client = make_client(analyst_narrator="llm", analyst_llm_model="mock-explainer-0.1")
    llm_report = llm_client.get(f"/api/v1/football/ai-analyst/{MATCH_ID}").json()["data"]
    assert llm_report["match_id"] == http_report["match_id"]
    assert llm_report["prediction"] == http_report["prediction"]
    assert llm_report["value"] == http_report["value"]
    assert llm_report["model_favorite"] == http_report["model_favorite"]
    assert llm_report["analyst"]["provider"] == "llm-v0.1"
    assert http_report["analyst"]["provider"] == "deterministic-v0.1"


def test_candidate_is_not_promoted_by_the_fullstack_surface() -> None:
    assert CANDIDATE_MODEL_VERSION == "football-elo-v1-candidate"
    assert CANDIDATE_STATUS == "candidate"
    assert VALUE_ENGINE_VERSION == "value-engine-0.1"
    source = ROUTER_SOURCE.read_text(encoding="utf-8")
    assert "/football/predictions/{match_id}" in source
    assert "/football/value/{match_id}" in source
    assert "/football/ai-picks" in source
    assert "/football/ai-analyst/{match_id}" in source
    assert "champion" not in source
