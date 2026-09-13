from app.core.config import Settings
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_settings import SettingsConfigDict


class TestSettings(Settings):
    model_config = SettingsConfigDict(env_prefix="PREDICTA_API_", env_file=None, extra="ignore")


def make_app(**overrides: object) -> FastAPI:
    values = {
        "env": "test",
        "data_mode": "mock",
        "repository": "mock",
        "log_level": "WARNING",
        "cors_origins": ["http://localhost:3000"],
        "mock_now": "2026-09-09T18:00:00Z",
        "auth_bypass": True,
    }
    values.update(overrides)
    return create_app(TestSettings(**values))  # type: ignore[arg-type]


def make_client(**overrides: object) -> TestClient:
    return TestClient(make_app(**overrides))
