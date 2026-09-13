from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.odds.exceptions import OddsUnavailableError
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import (
    FOOTBALL_1X2_MARKET,
    DataMode,
    Football1x2Selection,
    OddsSelection,
    OddsSnapshot,
)

MOCK_ODDS_SOURCE = "predicta-mock-odds-v0.1"
MOCK_MATCH_ID = "mth_football-sportmonks-19719892"
UNCONFIGURED_LIVE_ODDS_SOURCE = "unconfigured-live-odds-provider"


class OddsProvider(Protocol):
    @property
    def source(self) -> str: ...

    @property
    def data_mode(self) -> DataMode: ...

    def fetch(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]: ...


class MockOddsProvider:
    """Deterministic fictional fixture provider. It must never be advertised as live."""

    source = MOCK_ODDS_SOURCE
    data_mode: DataMode = "mock"

    def __init__(self, snapshots: tuple[OddsSnapshot, ...] | None = None) -> None:
        self._snapshots = snapshots if snapshots is not None else (_default_mock_snapshot(),)

    def fetch(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]:
        return tuple(
            snapshot
            for snapshot in self._snapshots
            if snapshot.match_id == match_id and snapshot.market == market
        )


class LiveOddsProvider:
    """Live football odds boundary. HTTP collection lives in the ingestion worker."""

    data_mode: DataMode = "live"

    def __init__(
        self,
        snapshots: tuple[OddsSnapshot, ...] | None = None,
        *,
        enable_live: bool = False,
        api_key: str = "",
    ) -> None:
        self._snapshots = snapshots
        self._enable_live = enable_live
        self._api_key = api_key.strip()

    @property
    def source(self) -> str:
        if self._configured:
            return LIVE_ODDS_SOURCE
        return UNCONFIGURED_LIVE_ODDS_SOURCE

    @property
    def _configured(self) -> bool:
        return self._enable_live and (self._snapshots is not None or bool(self._api_key))

    def fetch(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]:
        if not self._enable_live:
            raise OddsUnavailableError(
                "No live odds provider is configured; live odds are never synthesized."
            )
        if self._snapshots is not None:
            return tuple(
                snapshot
                for snapshot in self._snapshots
                if snapshot.match_id == match_id
                and snapshot.market == market
                and snapshot.data_mode == "live"
                and snapshot.source == LIVE_ODDS_SOURCE
            )
        if not self._api_key:
            raise OddsUnavailableError(
                "Live odds provider has no API key; live odds are never synthesized."
            )
        raise OddsUnavailableError(
            "Live football odds are ingested by the worker, not fetched by the API. "
            "There is no mock fallback."
        )


def _default_mock_snapshot() -> OddsSnapshot:
    collected_at = datetime.fromisoformat("2026-07-07T14:59:00+00:00")
    return OddsSnapshot(
        id="odd_mock_football_19719892_1x2_1459",
        provider_id="mock-football-19719892-1x2-1459",
        match_id=MOCK_MATCH_ID,
        bookmaker="Fictional Sportsbook",
        market=FOOTBALL_1X2_MARKET,
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("2.00")),
            OddsSelection(Football1x2Selection.DRAW, Decimal("4.00")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("5.00")),
        ),
        collected_at=collected_at,
        available_at=datetime.fromisoformat("2026-07-07T15:00:00+00:00"),
        source=MOCK_ODDS_SOURCE,
        data_mode="mock",
    )
