from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from tests.conftest import make_client

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"


def _spec() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _validate(schema_name: str, payload: dict) -> None:
    spec = _spec()
    document = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://predicta.local/openapi.yaml",
        "components": spec["components"],
    }
    resource = Resource.from_contents(document, default_specification=DRAFT202012)
    registry = Registry().with_resource(document["$id"], resource)
    schema = {"$ref": f"{document['$id']}#/components/schemas/{schema_name}"}
    Draft202012Validator(schema, registry=registry).validate(payload)


def test_openapi_paths_are_implemented() -> None:
    spec = _spec()
    client = make_client()
    implemented = {
        "/dashboard",
        "/sports",
        "/leagues",
        "/leagues/{league_id}",
        "/teams",
        "/teams/{team_id}",
        "/players",
        "/players/{player_id}",
        "/matches",
        "/matches/{match_id}",
        "/matches/{match_id}/stats",
        "/matches/{match_id}/odds",
        "/matches/{match_id}/prediction",
        "/football/predictions/{match_id}",
        "/football/value/{match_id}",
        "/picks",
        "/value",
        "/performance",
        "/ai/analyze",
    }
    assert set(spec["paths"]) == implemented
    for path in ("/dashboard", "/sports", "/matches", "/picks", "/value", "/performance"):
        assert client.get(f"/api/v1{path}").status_code == 200


def test_responses_match_openapi_envelopes() -> None:
    client = make_client()
    cases = [
        ("/api/v1/dashboard", "DashboardEnvelope"),
        ("/api/v1/sports", "SportsEnvelope"),
        ("/api/v1/leagues", "LeagueListEnvelope"),
        ("/api/v1/teams", "TeamListEnvelope"),
        ("/api/v1/players", "PlayerListEnvelope"),
        ("/api/v1/matches", "MatchListEnvelope"),
        ("/api/v1/picks", "PickListEnvelope"),
        ("/api/v1/value", "ValueListEnvelope"),
        ("/api/v1/performance", "PerformanceEnvelope"),
    ]
    for path, schema_name in cases:
        _validate(schema_name, client.get(path).json())
    _validate("MatchDetailEnvelope", client.get("/api/v1/matches/mth_northgate_harbor").json())
    _validate(
        "FootballValueAnalysisEnvelope",
        client.get("/api/v1/football/value/mth_football-sportmonks-19719892").json(),
    )
    _validate(
        "AnalystEnvelope",
        client.post(
            "/api/v1/ai/analyze",
            json={"match_id": "mth_northgate_harbor", "question": "Explain the probabilities."},
        ).json(),
    )
    _validate("ProblemDetails", client.get("/api/v1/players/missing").json())
