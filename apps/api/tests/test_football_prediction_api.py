from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from tests.conftest import make_client

LIVE_MATCH_ID = "mth_football-sportmonks-19719892"
CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"


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
    assert body["data_mode"] == "live"
    data = body["data"]
    assert data["model_status"] == "candidate"
    assert data["model_version"] == "football-elo-v1-candidate"
    assert data["dataset_version"] == "football-1x2-history-0.3"
    assert data["feature_schema_version"] == "football-1x2-features-0.3"
    total = data["home_probability"] + data["draw_probability"] + data["away_probability"]
    assert total == pytest.approx(1.0, abs=1e-9)
    assert "expected_value" not in data
    _validate("FootballModelPredictionEnvelope", body)
    again = client.get(f"/api/v1/football/predictions/{LIVE_MATCH_ID}").json()["data"]
    assert again["home_probability"] == data["home_probability"]
    assert again["draw_probability"] == data["draw_probability"]
    assert again["away_probability"] == data["away_probability"]


def test_published_frontend_prediction_contract_is_unchanged() -> None:
    client = make_client()
    response = client.get("/api/v1/matches/mth_northgate_harbor/prediction")
    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == "mock"
    assert body["data"]["outcomes"]
    assert "home_probability" not in body["data"]


def test_missing_artefact_returns_rfc9457(tmp_path: Path) -> None:
    client = make_client(football_registry_dir=tmp_path)
    response = client.get(f"/api/v1/football/predictions/{LIVE_MATCH_ID}")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "/problems/model-artefact-not-found"
    assert body["status"] == 503
    assert "request_id" in body
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_pit_unavailable_returns_rfc9457() -> None:
    client = make_client()
    response = client.get("/api/v1/football/predictions/mth_does_not_exist")
    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "/problems/pit-features-unavailable"
    assert "request_id" in body


def test_cutoff_after_kickoff_returns_temporal_leakage() -> None:
    client = make_client()
    response = client.get(
        f"/api/v1/football/predictions/{LIVE_MATCH_ID}",
        params={"cutoff_at": "2026-07-07T16:00:01Z"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["type"] == "/problems/temporal-leakage"
