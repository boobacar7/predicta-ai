from __future__ import annotations

from datetime import datetime
from typing import Protocol

from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.raw.envelope import RawEnvelope


class ProviderRequest:
    def __init__(
        self,
        *,
        resource: ResourceType,
        sport: SportCode | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        cursor: str | None = None,
        league: str | None = None,
        season: str | None = None,
    ) -> None:
        self.resource = resource
        self.sport = sport
        self.since = since
        self.until = until
        self.cursor = cursor
        self.league = league
        self.season = season


class ProviderHealth:
    def __init__(self, *, name: str, connected: bool, detail: str) -> None:
        self.name = name
        self.connected = connected
        self.detail = detail


class FootballProvider(Protocol):
    name: str

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]: ...

    def health(self) -> ProviderHealth: ...


class BasketballProvider(Protocol):
    name: str

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]: ...

    def health(self) -> ProviderHealth: ...


class TennisProvider(Protocol):
    name: str

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]: ...

    def health(self) -> ProviderHealth: ...


class OddsProvider(Protocol):
    name: str

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]: ...

    def health(self) -> ProviderHealth: ...


class SportsProvider(Protocol):
    """Union-style protocol used by the pipeline; sport adapters satisfy it."""

    name: str

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]: ...

    def health(self) -> ProviderHealth: ...
