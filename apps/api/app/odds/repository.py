from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Protocol

from app.odds.types import OddsSnapshot


class OddsRepository(Protocol):
    def append(self, snapshot: OddsSnapshot) -> None: ...

    def history(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]: ...


class InMemoryOddsRepository:
    """Append-only repository used by tests and the explicit mock provider."""

    def __init__(self) -> None:
        self._snapshots: dict[str, OddsSnapshot] = {}
        self._provider_ids: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def append(self, snapshot: OddsSnapshot) -> None:
        provider_key = (snapshot.source, snapshot.provider_id)
        with self._lock:
            existing = self._snapshots.get(snapshot.id)
            existing_id = self._provider_ids.get(provider_key)
            if existing == snapshot and (existing_id is None or existing_id == snapshot.id):
                return
            if existing is not None or existing_id is not None:
                raise ValueError("Odds snapshots are immutable and cannot be overwritten.")
            self._snapshots[snapshot.id] = snapshot
            self._provider_ids[provider_key] = snapshot.id

    def history(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]:
        with self._lock:
            snapshots = (
                item
                for item in self._snapshots.values()
                if item.match_id == match_id and item.market == market
            )
            return tuple(sorted(snapshots, key=_snapshot_order))


def _snapshot_order(snapshot: OddsSnapshot) -> tuple[datetime, datetime, str]:
    return (snapshot.available_at, snapshot.collected_at, snapshot.id)
