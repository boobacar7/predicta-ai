from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.odds.exceptions import OddsUnavailableError
from app.odds.types import (
    FOOTBALL_1X2_MARKET,
    DataMode,
    Football1x2Selection,
    OddsSelection,
    OddsSnapshot,
)

MOCK_ODDS_SOURCE = "predicta-mock-odds-v0.1"
MOCK_MATCH_ID = "mth_football-sportmonks-19719892"


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
    """Provider-neutral live boundary. A real adapter will implement this contract later."""

    source = "unconfigured-live-odds-provider"
    data_mode: DataMode = "live"

    def fetch(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]:
        raise OddsUnavailableError(
            "No live odds provider is configured; live odds are never synthesized."
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
