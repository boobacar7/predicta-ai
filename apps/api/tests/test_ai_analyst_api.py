from __future__ import annotations

from pathlib import Path

import yaml
from app.ai_analyst.models import CONFIDENCE_RULE
from httpx import Response
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from tests.conftest import make_client

MATCH_ID = "mth_football-sportmonks-19719892"
KICKOFF = "2026-07-07T16:00:00Z"
CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"
FORBIDDEN = ("guaranteed", "safe bet", "sure win", "certain", "pari sûr", "gain garanti", "blessure")


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
    assert response.headers["X-Request-ID"] == body["request_id"]
    _validate("ProblemDetails", body)
    return body


def test_football_ai_analyst_complete_mock_context() -> None:
    client = make_client()
    response = client.get(
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
        headers={"X-Request-ID": "req_ai_analyst"},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_ai_analyst"
    body = response.json()
    assert body["request_id"] == "req_ai_analyst"
    assert body["data_mode"] == "mock"
    data = body["data"]
    assert data["match_id"] == MATCH_ID
    assert data["home_team"] == "Lincoln Red Imps"
    assert data["away_team"] == "Inter Club d'Escaldes"
    assert data["kickoff_at"] == KICKOFF
    assert data["prediction"]["model_status"] == "candidate"
    assert data["prediction"]["model_version"] == "football-elo-v1-candidate"
    assert data["prediction"]["dataset_version"] == "football-1x2-history-0.3"
    assert data["prediction"]["cutoff_at"] == KICKOFF
    assert data["model_favorite"] == "HOME"
    assert data["value"]["availability"] == "available"
    assert data["value"]["selection"] == "HOME"
    assert data["value"]["value_selection"] == "AWAY"
    assert data["model_favorite"] != data["value"]["value_selection"]
    assert data["value"]["value_engine_version"] == "value-engine-0.1"
    assert data["analyst"]["analysis_version"] == "ai-analyst-0.1"
    assert data["analyst"]["provider"] == "deterministic-v0.1"
    assert data["analyst"]["confidence"]["level"] == "medium"
    assert data["analyst"]["confidence"]["rule"] == CONFIDENCE_RULE
    assert data["analyst"]["data_quality"]["data_mode"] == "mock"
    assert data["analyst"]["data_quality"]["model_status"] == "candidate"
    assert data["analyst"]["confidence"]["level"] != "high"
    serialized = response.text.casefold()
    assert not any(term in serialized for term in FORBIDDEN)
    _validate("FootballAiAnalystEnvelope", body)
    again = client.get(
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
        params={"cutoff_at": KICKOFF},
        headers={"X-Request-ID": "req_ai_analyst_2"},
    ).json()["data"]
    assert again["prediction"] == data["prediction"]
    assert again["value"] == data["value"]
    assert again["analyst"]["summary"] == data["analyst"]["summary"]
    assert again["analyst"]["key_factors"] == data["analyst"]["key_factors"]
    assert again["analyst"]["generated_at"] == data["analyst"]["generated_at"]


def test_football_ai_analyst_rfc9457_errors() -> None:
    client = make_client()
    _assert_problem(
        client.get("/api/v1/football/ai-analyst/mth_does_not_exist", headers={"X-Request-ID": "req_missing"}),
        status=404,
        type_uri="/problems/not-found",
    )
    _assert_problem(
        client.get(
            f"/api/v1/football/ai-analyst/{MATCH_ID}",
            params={"cutoff_at": "2026-07-07T15:59:59Z"},
            headers={"X-Request-ID": "req_early"},
        ),
        status=422,
        type_uri="/problems/pit-features-unavailable",
    )
    _assert_problem(
        client.get(
            f"/api/v1/football/ai-analyst/{MATCH_ID}",
            params={"cutoff_at": "2026-07-07T16:00:01Z"},
            headers={"X-Request-ID": "req_late"},
        ),
        status=409,
        type_uri="/problems/temporal-leakage",
    )
    _assert_problem(
        client.get(
            f"/api/v1/football/ai-analyst/{MATCH_ID}",
            params={"cutoff_at": "not-a-timestamp"},
            headers={"X-Request-ID": "req_invalid"},
        ),
        status=400,
        type_uri="/problems/validation",
    )


def test_missing_artefact_is_not_replaced_by_mock_analysis(tmp_path: Path) -> None:
    client = make_client(football_registry_dir=tmp_path)
    _assert_problem(
        client.get(f"/api/v1/football/ai-analyst/{MATCH_ID}", headers={"X-Request-ID": "req_artefact"}),
        status=503,
        type_uri="/problems/model-artefact-not-found",
    )


def test_historical_match_details_and_analyst_share_identity() -> None:
    client = make_client()
    match = client.get(f"/api/v1/matches/{MATCH_ID}").json()["data"]
    analyst = client.get(f"/api/v1/football/ai-analyst/{MATCH_ID}").json()["data"]
    assert match["match_id"] == analyst["match_id"] == MATCH_ID
    assert match["home_team"] == analyst["home_team"] == "Lincoln Red Imps"
    assert match["away_team"] == analyst["away_team"] == "Inter Club d'Escaldes"
    assert match["league"] == analyst["league"] == "Champions League"
    assert match["kickoff_at"] == analyst["kickoff_at"] == KICKOFF


def test_football_ai_analyst_respects_pit_microseconds() -> None:
    client = make_client()
    _assert_problem(
        client.get(
            f"/api/v1/football/ai-analyst/{MATCH_ID}",
            params={"cutoff_at": "2026-07-07T15:59:59.999999Z"},
            headers={"X-Request-ID": "req_pit_before"},
        ),
        status=422,
        type_uri="/problems/pit-features-unavailable",
    )
    exact = client.get(
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
        params={"cutoff_at": KICKOFF},
        headers={"X-Request-ID": "req_pit_exact"},
    )
    assert exact.status_code == 200
    assert exact.json()["data"]["match_id"] == MATCH_ID
    assert exact.json()["data"]["kickoff_at"] == KICKOFF
    _assert_problem(
        client.get(
            f"/api/v1/football/ai-analyst/{MATCH_ID}",
            params={"cutoff_at": "2026-07-07T16:00:00.000001Z"},
            headers={"X-Request-ID": "req_pit_after"},
        ),
        status=409,
        type_uri="/problems/temporal-leakage",
    )


def test_openapi_declares_football_ai_analyst() -> None:
    spec = yaml.safe_load(CONTRACT.read_text())
    assert "/football/ai-analyst/{match_id}" in spec["paths"]
    assert spec["components"]["schemas"]["FootballAnalystExplanation"]["properties"]["provider"]["enum"] == [
        "deterministic-v0.1",
        "llm-v0.1",
    ]


def test_llm_narrator_stays_behind_the_same_http_boundary() -> None:
    client = make_client(analyst_narrator="llm", analyst_llm_model="mock-explainer-0.1")
    response = client.get(
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
        headers={"X-Request-ID": "req_ai_analyst_llm"},
    )
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert body["data_mode"] == "mock"
    assert data["analyst"]["provider"] == "llm-v0.1"
    assert data["analyst"]["data_quality"]["data_mode"] == "mock"
    assert data["prediction"]["model_version"] == "football-elo-v1-candidate"
    assert data["prediction"]["cutoff_at"] == KICKOFF
    assert data["model_favorite"] == "HOME"
    assert data["value"]["value_selection"] == "AWAY"
    assert "mock" in data["analyst"]["summary"].casefold()
    serialized = response.text.casefold()
    assert not any(term in serialized for term in FORBIDDEN)
    _validate("FootballAiAnalystEnvelope", body)


def test_llm_narrator_cannot_invert_lincoln_favorite_and_value() -> None:
    client = make_client(analyst_narrator="llm", analyst_llm_model="mock-explainer-0.1")
    data = client.get(f"/api/v1/football/ai-analyst/{MATCH_ID}").json()["data"]
    assert data["home_team"] == "Lincoln Red Imps"
    assert data["away_team"] == "Inter Club d'Escaldes"
    assert data["model_favorite"] == "HOME"
    assert data["value"]["value_selection"] == "AWAY"
    assert data["model_favorite"] != data["value"]["value_selection"]
    summary = data["analyst"]["summary"].casefold()
    assert "away is the model favorite" not in summary
    assert "home is the best value" not in summary


def test_llm_narrator_respects_pit_microseconds() -> None:
    client = make_client(analyst_narrator="llm", analyst_llm_model="mock-explainer-0.1")
    _assert_problem(
        client.get(
            f"/api/v1/football/ai-analyst/{MATCH_ID}",
            params={"cutoff_at": "2026-07-07T15:59:59.999999Z"},
            headers={"X-Request-ID": "req_llm_pit_before"},
        ),
        status=422,
        type_uri="/problems/pit-features-unavailable",
    )
    exact = client.get(
        f"/api/v1/football/ai-analyst/{MATCH_ID}",
        params={"cutoff_at": KICKOFF},
        headers={"X-Request-ID": "req_llm_pit_exact"},
    )
    assert exact.status_code == 200
    assert exact.json()["data"]["prediction"]["cutoff_at"] == KICKOFF
    assert exact.json()["data_mode"] == "mock"
    _assert_problem(
        client.get(
            f"/api/v1/football/ai-analyst/{MATCH_ID}",
            params={"cutoff_at": "2026-07-07T16:00:00.000001Z"},
            headers={"X-Request-ID": "req_llm_pit_after"},
        ),
        status=409,
        type_uri="/problems/temporal-leakage",
    )
