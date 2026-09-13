from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from app.predictions.simplex import renormalize_1x2
from httpx import Response
from jsonschema import Draft202012Validator
from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.registry.artifact import load_registry
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from tests.conftest import make_client
from tests.live_assets import requires_football_http, requires_live_assets, requires_pit_dataset

LIVE_MATCH_ID = "mth_football-sportmonks-19719892"
LIVE_KICKOFF = "2026-07-07T16:00:00Z"
REPO = Path(__file__).resolve().parents[3]
CONTRACT = REPO / "contracts" / "openapi.yaml"
DATASET = REPO / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
ARTEFACT = REPO / "workers" / "ml" / "var" / "registry" / "football-elo-v1-candidate" / "artefact.joblib"
PARITY_MATCHES: tuple[tuple[str, str], ...] = (
    ("Premier League", "mth_football-sportmonks-19722183"),
    ("Ligue 1", "mth_football-sportmonks-19715615"),
    ("La Liga", "mth_football-sportmonks-19732709"),
    ("Bundesliga", "mth_football-sportmonks-19735185"),
    ("Serie A", "mth_football-sportmonks-19713588"),
    ("Champions League", "mth_football-sportmonks-19873242"),
    ("Major League Soccer", "mth_football-sportmonks-19609793"),
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
    assert "data_mode" not in body
    assert "data" not in body
    assert response.headers["X-Request-ID"] == body["request_id"]
    _validate("ProblemDetails", body)
    return body


@requires_live_assets
def test_football_prediction_live_candidate_response() -> None:
    client = make_client()
    response = client.get(
        f"/api/v1/football/predictions/{LIVE_MATCH_ID}",
        headers={"X-Request-ID": "req_football_pred"},
    )
    assert response.status_code == 200
    body = response.json()
    assert response.headers["X-Request-ID"] == "req_football_pred"
    assert body["request_id"] == "req_football_pred"
    frame = load_football_dataset(DATASET).frame
    pit_data_mode = str(frame.loc[frame["match_id"] == LIVE_MATCH_ID, "data_mode"].iloc[0])
    assert pit_data_mode == "live"
    assert body["data_mode"] == pit_data_mode
    data = body["data"]
    assert data["model_status"] == "candidate"
    assert data["model_status"] != "champion"
    assert data["model_version"] == "football-elo-v1-candidate"
    assert data["dataset_version"] == "football-1x2-history-0.3"
    assert data["feature_schema_version"] == "football-1x2-features-0.3"
    assert data["cutoff_policy"] == "pre_kickoff"
    total = data["home_probability"] + data["draw_probability"] + data["away_probability"]
    assert total == pytest.approx(1.0, abs=1e-9)
    for key in ("home_probability", "draw_probability", "away_probability"):
        assert 0.0 < data[key] < 1.0
    assert "expected_value" not in data
    _validate("FootballModelPredictionEnvelope", body)
    again = client.get(
        f"/api/v1/football/predictions/{LIVE_MATCH_ID}",
        params={"cutoff_at": LIVE_KICKOFF},
    ).json()["data"]
    assert again["home_probability"] == data["home_probability"]
    assert again["draw_probability"] == data["draw_probability"]
    assert again["away_probability"] == data["away_probability"]


@requires_live_assets
def test_ml_reference_and_api_probabilities_match_across_competitions() -> None:
    frame = load_football_dataset(DATASET).frame
    artefact = load_registry(ARTEFACT)
    client = make_client()
    for competition, match_id in PARITY_MATCHES:
        row = frame.loc[frame["match_id"] == match_id].iloc[0]
        assert str(row["competition"]) == competition
        diffs = np.array([float(row["elo_diff"])], dtype=np.float64)
        raw = np.asarray(artefact["predictors"]["elo"].predict_diffs(diffs), dtype=np.float64)
        calibrated = np.asarray(artefact["calibrators"]["elo"].transform(raw), dtype=np.float64)
        expected = renormalize_1x2(float(calibrated[0][0]), float(calibrated[0][1]), float(calibrated[0][2])).as_tuple()
        response = client.get(f"/api/v1/football/predictions/{match_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        api = (data["home_probability"], data["draw_probability"], data["away_probability"])
        assert api == expected
        assert sum(api) == pytest.approx(1.0, abs=1e-12)


def test_published_frontend_prediction_contract_is_unchanged() -> None:
    client = make_client()
    response = client.get("/api/v1/matches/mth_northgate_harbor/prediction")
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == "mock"
    assert body["data"]["outcomes"]
    assert "home_probability" not in body["data"]


@requires_pit_dataset
def test_missing_artefact_returns_rfc9457(tmp_path: Path) -> None:
    client = make_client(football_registry_dir=tmp_path)
    response = client.get(f"/api/v1/football/predictions/{LIVE_MATCH_ID}")
    _assert_problem(response, status=503, type_uri="/problems/model-artefact-not-found")


@requires_live_assets
def test_pit_unavailable_returns_rfc9457() -> None:
    client = make_client()
    response = client.get("/api/v1/football/predictions/mth_does_not_exist")
    _assert_problem(response, status=422, type_uri="/problems/pit-features-unavailable")


@requires_live_assets
def test_cutoff_before_kickoff_returns_pit_unavailable() -> None:
    client = make_client()
    response = client.get(
        f"/api/v1/football/predictions/{LIVE_MATCH_ID}",
        params={"cutoff_at": "2026-07-07T15:59:59Z"},
    )
    _assert_problem(response, status=422, type_uri="/problems/pit-features-unavailable")


@requires_live_assets
def test_cutoff_after_kickoff_returns_temporal_leakage() -> None:
    client = make_client()
    response = client.get(
        f"/api/v1/football/predictions/{LIVE_MATCH_ID}",
        params={"cutoff_at": "2026-07-07T16:00:01Z"},
    )
    _assert_problem(response, status=409, type_uri="/problems/temporal-leakage")


@requires_football_http
def test_prediction_envelope_follows_pit_not_odds_runtime() -> None:
    client = make_client()
    prediction = client.get(f"/api/v1/football/predictions/{LIVE_MATCH_ID}").json()
    value = client.get(f"/api/v1/football/value/{LIVE_MATCH_ID}").json()
    picks = client.get("/api/v1/football/ai-picks").json()
    analyst = client.get(f"/api/v1/football/ai-analyst/{LIVE_MATCH_ID}").json()
    catalog = client.get("/api/v1/matches/mth_northgate_harbor/prediction").json()
    assert prediction["data_mode"] == "live"
    assert value["data_mode"] == "mock"
    assert value["data"]["metadata"]["data_mode"] == "mock"
    assert picks["data_mode"] == "mock"
    assert all(item["data_mode"] == "mock" for item in picks["data"]["items"])
    assert analyst["data_mode"] == "mock"
    assert analyst["data"]["analyst"]["data_quality"]["data_mode"] == "mock"
    assert catalog["data_mode"] == "mock"


def test_prediction_router_does_not_hardcode_live_envelope() -> None:
    source = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "router.py"
    text = source.read_text()
    assert 'data_mode="live"' not in text
    assert "data_mode='live'" not in text


@requires_football_http
def test_lincoln_value_invariants_remain_after_prediction_provenance_fix() -> None:
    client = make_client()
    analyst = client.get(f"/api/v1/football/ai-analyst/{LIVE_MATCH_ID}").json()["data"]
    value = client.get(f"/api/v1/football/value/{LIVE_MATCH_ID}").json()["data"]
    assert analyst["model_favorite"] == "HOME"
    assert analyst["value"]["value_selection"] == "AWAY"
    assert value["value"]["home"]["ev"] == pytest.approx(-0.167, abs=1e-3)
    assert value["value"]["away"]["ev"] == pytest.approx(0.563, abs=1e-3)

