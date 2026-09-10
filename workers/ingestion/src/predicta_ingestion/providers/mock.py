from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.clock import Clock
from predicta_ingestion.config import FIXTURES_DIR
from predicta_ingestion.providers.protocols import ProviderHealth, ProviderRequest
from predicta_ingestion.raw.envelope import RawEnvelope


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Fixture root must be an object: {path}")
    if payload.get("data_mode") != "mock":
        raise RuntimeError(f"Ingestion fixtures must declare data_mode=mock: {path}")
    return payload


def _envelope(
    *,
    provider: str,
    resource: ResourceType,
    sport: SportCode,
    clock: Clock,
    payload: dict[str, Any],
    request_key: str,
) -> RawEnvelope:
    return RawEnvelope(
        provider=provider,
        resource=resource,
        request_key=request_key,
        collected_at=clock.now(),
        data_mode=DataMode.MOCK,
        sport=sport,
        body=json.dumps(payload).encode("utf-8"),
    )


class MockFootballProvider:
    name = "mock.api_football"

    def __init__(self, clock: Clock, fixtures_dir: Path | None = None) -> None:
        self._clock = clock
        self._path = (fixtures_dir or FIXTURES_DIR) / "football_bundle.json"

    def health(self) -> ProviderHealth:
        return ProviderHealth(name=self.name, connected=True, detail="mock fixtures only")

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]:
        payload = _load(self._path)
        return [
            _envelope(
                provider=self.name,
                resource=request.resource,
                sport=SportCode.FOOTBALL,
                clock=self._clock,
                payload=payload,
                request_key=f"football:{request.resource.value}",
            )
        ]


class MockBasketballProvider:
    name = "mock.balldontlie"

    def __init__(self, clock: Clock, fixtures_dir: Path | None = None) -> None:
        self._clock = clock
        self._path = (fixtures_dir or FIXTURES_DIR) / "basketball_games.json"

    def health(self) -> ProviderHealth:
        return ProviderHealth(name=self.name, connected=True, detail="mock fixtures only")

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]:
        payload = _load(self._path)
        return [
            _envelope(
                provider=self.name,
                resource=request.resource,
                sport=SportCode.BASKETBALL,
                clock=self._clock,
                payload=payload,
                request_key=f"basketball:{request.resource.value}",
            )
        ]


class MockTennisProvider:
    name = "mock.api_tennis"

    def __init__(self, clock: Clock, fixtures_dir: Path | None = None) -> None:
        self._clock = clock
        self._path = (fixtures_dir or FIXTURES_DIR) / "tennis_matches.json"

    def health(self) -> ProviderHealth:
        return ProviderHealth(name=self.name, connected=True, detail="mock fixtures only")

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]:
        payload = _load(self._path)
        return [
            _envelope(
                provider=self.name,
                resource=request.resource,
                sport=SportCode.TENNIS,
                clock=self._clock,
                payload=payload,
                request_key=f"tennis:{request.resource.value}",
            )
        ]


class MockOddsProvider:
    name = "mock.the_odds_api"

    def __init__(self, clock: Clock, fixtures_dir: Path | None = None) -> None:
        self._clock = clock
        self._path = (fixtures_dir or FIXTURES_DIR) / "odds_snapshots.json"

    def health(self) -> ProviderHealth:
        return ProviderHealth(name=self.name, connected=True, detail="mock fixtures only")

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]:
        payload = _load(self._path)
        return [
            _envelope(
                provider=self.name,
                resource=ResourceType.ODDS,
                sport=request.sport or SportCode.FOOTBALL,
                clock=self._clock,
                payload=payload,
                request_key="odds:mock",
            )
        ]
