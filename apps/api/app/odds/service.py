from __future__ import annotations

from datetime import datetime

from app.odds.exceptions import (
    IncompleteOddsMarketError,
    OddsTemporalLeakageError,
    OddsUnavailableError,
)
from app.odds.providers import OddsProvider
from app.odds.repository import OddsRepository
from app.odds.types import FOOTBALL_1X2_MARKET, Football1x2Selection, OddsSnapshot, is_complete_football_1x2


class OddsService:
    def __init__(self, *, provider: OddsProvider, repository: OddsRepository) -> None:
        self._provider = provider
        self._repository = repository

    def market_at(
        self,
        *,
        match_id: str,
        market: str,
        cutoff_at: datetime,
    ) -> OddsSnapshot:
        try:
            fetched = self._provider.fetch(match_id, market)
        except OddsUnavailableError:
            fetched = ()

        for snapshot in fetched:
            if snapshot.data_mode != self._provider.data_mode:
                raise OddsUnavailableError("Odds provider returned an inconsistent data_mode.")
            if snapshot.source != self._provider.source:
                raise OddsUnavailableError("Odds provider returned an inconsistent source.")
            self._repository.append(snapshot)

        history = self._repository.history(
            match_id,
            market,
            source=self._provider.source,
            data_mode=self._provider.data_mode,
        )
        eligible = tuple(item for item in history if item.available_at <= cutoff_at)
        if not eligible:
            if any(item.available_at > cutoff_at for item in history):
                raise OddsTemporalLeakageError(
                    "Odds exist for this market, but every snapshot became available after cutoff_at."
                )
            raise OddsUnavailableError("No odds snapshot is available for this match and market.")

        complete = tuple(item for item in eligible if is_complete_football_1x2(item))
        snapshot = complete[-1] if complete else eligible[-1]
        self._validate_complete_market(snapshot)
        return snapshot

    @staticmethod
    def _validate_complete_market(snapshot: OddsSnapshot) -> None:
        if snapshot.market != FOOTBALL_1X2_MARKET:
            raise IncompleteOddsMarketError("Only the football 1X2 market is supported.")
        actual = {item.selection for item in snapshot.selections}
        expected = set(Football1x2Selection)
        if actual != expected:
            missing = ", ".join(sorted(selection.value for selection in expected - actual))
            raise IncompleteOddsMarketError(
                f"Football 1X2 market is incomplete. Missing selections: {missing or 'unknown'}."
            )
