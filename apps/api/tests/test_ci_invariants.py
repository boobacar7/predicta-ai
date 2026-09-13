from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import joblib
import pytest
import yaml
from app.core.config import Settings
from app.odds.exceptions import OddsUnavailableError
from app.odds.providers import MOCK_MATCH_ID, LiveOddsProvider, MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.types import Football1x2Selection
from app.predictions.exceptions import ArtefactNotFoundError
from app.predictions.models import load_football_1x2_model
from app.predictions.types import CANDIDATE_MODEL_VERSION, CANDIDATE_STATUS
from app.value_engine.calculator import (
    VALUE_ENGINE_VERSION,
    edge,
    expected_value,
    implied_probability,
    no_vig_probabilities,
    overround,
)

REPO = Path(__file__).resolve().parents[3]
CONTRACT = REPO / "contracts" / "openapi.yaml"
ROUTER = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "router.py"
FOOTBALL_PATHS = (
    "/football/predictions/{match_id}",
    "/football/value/{match_id}",
    "/football/ai-picks",
    "/football/ai-analyst/{match_id}",
)


def test_live_odds_provider_never_synthesizes_odds() -> None:
    live = LiveOddsProvider()
    mock = MockOddsProvider()
    assert live.data_mode == "live"
    assert mock.data_mode == "mock"
    with pytest.raises(OddsUnavailableError, match="never synthesized"):
        live.fetch(MOCK_MATCH_ID, "1X2")
    assert mock.fetch(MOCK_MATCH_ID, "1X2")


def test_live_odds_http_gap_does_not_fallback_to_mock() -> None:
    service = OddsService(provider=LiveOddsProvider(), repository=InMemoryOddsRepository())
    with pytest.raises(OddsUnavailableError):
        service.market_at(
            match_id=MOCK_MATCH_ID,
            market="1X2",
            cutoff_at=datetime(2026, 7, 7, 16, tzinfo=UTC),
        )


def test_prediction_router_does_not_hardcode_live_data_mode() -> None:
    text = ROUTER.read_text(encoding="utf-8")
    assert 'data_mode="live"' not in text
    assert "data_mode='live'" not in text


def test_default_runtime_keeps_mock_identifiable() -> None:
    settings = Settings(_env_file=None, env="test")
    assert settings.data_mode == "mock"
    assert settings.repository == "mock"
    assert settings.resolved_data_mode() == "mock"
    assert settings.football_model_version == CANDIDATE_MODEL_VERSION
    assert settings.analyst_llm_model == "mock-explainer-0.1"


def test_champion_and_production_artefacts_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ArtefactNotFoundError, match="is not served"):
        load_football_1x2_model(registry_dir=tmp_path, model_version="football-elo-v1-champion")
    directory = tmp_path / CANDIDATE_MODEL_VERSION
    directory.mkdir()
    joblib.dump(
        {
            "status": "production",
            "selected": "elo",
            "predictors": {"elo": object()},
            "dataset_version": "football-1x2-history-0.3",
        },
        directory / "artefact.joblib",
    )
    (directory / "registry.json").write_text(
        json.dumps(
            {
                "status": "production",
                "model_version": CANDIDATE_MODEL_VERSION,
                "dataset_version": "football-1x2-history-0.3",
                "feature_schema_version": "football-1x2-features-0.3",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ArtefactNotFoundError, match="not production"):
        load_football_1x2_model(registry_dir=tmp_path, model_version=CANDIDATE_MODEL_VERSION)
    assert CANDIDATE_STATUS == "candidate"
    assert CANDIDATE_STATUS != "champion"


def test_canonical_value_engine_formula_is_unique() -> None:
    odds = {
        Football1x2Selection.HOME: Decimal("2.00"),
        Football1x2Selection.DRAW: Decimal("4.00"),
        Football1x2Selection.AWAY: Decimal("5.00"),
    }
    implied = {selection: implied_probability(price) for selection, price in odds.items()}
    market_overround = overround(tuple(odds.values()))
    no_vig, returned_overround = no_vig_probabilities(odds)
    assert VALUE_ENGINE_VERSION == "value-engine-0.1"
    assert market_overround == sum(implied.values(), Decimal(0))
    assert returned_overround == market_overround
    assert market_overround != market_overround - Decimal(1)
    for selection, _price in odds.items():
        assert no_vig[selection] == implied[selection] / market_overround
    assert edge(Decimal("0.60"), Decimal("0.5")) == Decimal("0.10")
    assert expected_value(Decimal("0.60"), Decimal("2.00")) == Decimal("0.20")


def test_openapi_declares_football_product_paths() -> None:
    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    for path in FOOTBALL_PATHS:
        assert path in spec["paths"]
    generated = (REPO / "apps" / "web" / "src" / "types" / "generated" / "api.ts").read_text(encoding="utf-8")
    for path in FOOTBALL_PATHS:
        assert f'"{path}"' in generated
