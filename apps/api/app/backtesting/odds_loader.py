from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.backtesting.matching import decide_events
from app.backtesting.types import (
    CatalogMatch,
    OddsBundle,
    QualityExclusion,
    QualityLedger,
)
from app.odds.the_odds_api import LIVE_ODDS_SOURCE, map_the_odds_api_events
from app.odds.types import Football1x2Selection, OddsSnapshot, is_complete_football_1x2


def load_historical_events(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError(f"Historical odds fixture {path} does not contain a data list.")
        for event in data:
            if isinstance(event, dict):
                events.append(event)
    return events


def inspect_bookmakers(event: dict[str, Any], quality: QualityLedger, *, matched: bool) -> None:
    event_id = str(event.get("id") or "")
    books = event.get("bookmakers")
    if not isinstance(books, list):
        quality.add(
            QualityExclusion(
                kind="incomplete_market",
                detail="Bookmakers must be a list.",
                event_id=event_id,
            )
        )
        return
    for book in books:
        if not isinstance(book, dict):
            quality.add(
                QualityExclusion(
                    kind="incomplete_market",
                    detail="Bookmaker must be an object.",
                    event_id=event_id,
                )
            )
            continue
        book_key = str(book.get("key") or "")
        if not book.get("last_update"):
            quality.add(
                QualityExclusion(
                    kind="missing_timestamp",
                    detail="Bookmaker last_update is missing; availability is never invented.",
                    event_id=event_id,
                    bookmaker=book_key or None,
                )
            )
            continue
        if not matched:
            continue
        markets = book.get("markets")
        if not isinstance(markets, list):
            quality.add(
                QualityExclusion(
                    kind="incomplete_market",
                    detail="Markets must be a list.",
                    event_id=event_id,
                    bookmaker=book_key or None,
                )
            )


def snapshots_for_matched_event(
    event: dict[str, Any],
    *,
    match_id: str,
    raw_payload_id: str,
    quality: QualityLedger,
) -> list[OddsSnapshot]:
    mapped = map_the_odds_api_events(
        [event],
        match_id=match_id,
        market="1X2",
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
        raw_payload_id=raw_payload_id,
    )
    accepted: list[OddsSnapshot] = []
    for snapshot in mapped:
        if not is_complete_football_1x2(snapshot):
            missing = sorted(
                selection.value
                for selection in Football1x2Selection
                if selection not in {item.selection for item in snapshot.selections}
            )
            quality.add(
                QualityExclusion(
                    kind="incomplete_market",
                    detail=f"Football 1X2 market is incomplete. Missing: {', '.join(missing) or 'unknown'}.",
                    event_id=str(event.get("id") or ""),
                    match_id=match_id,
                    bookmaker=snapshot.bookmaker,
                )
            )
            continue
        accepted.append(snapshot)
        quality.snapshots_accepted += 1
        if snapshot.bookmaker not in quality.bookmakers_seen:
            quality.bookmakers_seen.append(snapshot.bookmaker)
    quality.bookmakers_seen.sort()
    return accepted


def load_fixture_odds(
    paths: tuple[Path, ...],
    catalog: tuple[CatalogMatch, ...],
    extra_events: list[dict[str, Any]] | None = None,
) -> OddsBundle:
    events = load_historical_events(paths)
    if extra_events:
        events.extend(extra_events)
    quality = QualityLedger()
    decisions = decide_events(events, catalog, quality)
    by_id = {item.event_id: item for item in decisions}
    snapshots: list[OddsSnapshot] = []
    for event in events:
        event_id = str(event.get("id") or "")
        decision = by_id.get(event_id)
        if decision is None:
            continue
        inspect_bookmakers(event, quality, matched=decision.match_id is not None)
        if decision.match_id is None:
            continue
        snapshots.extend(
            snapshots_for_matched_event(
                event,
                match_id=decision.match_id,
                raw_payload_id=f"raw_fixture_{event_id}",
                quality=quality,
            )
        )
    return OddsBundle(snapshots=tuple(snapshots), decisions=tuple(decisions), quality=quality)


def inverted_psg_rennes_event() -> dict[str, Any]:
    """Provider orientation PSG home vs canonical Rennes home. Must not match."""

    return {
        "id": "fl1_psg_rennes_inverted_pilot",
        "sport_key": "soccer_france_ligue_one",
        "commence_time": "2026-08-23T18:45:00Z",
        "home_team": "Paris Saint Germain",
        "away_team": "Rennes",
        "bookmakers": [
            {
                "key": "pinnacle",
                "last_update": "2026-08-16T10:54:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Paris Saint Germain", "price": 1.45},
                            {"name": "Draw", "price": 4.40},
                            {"name": "Rennes", "price": 6.50},
                        ],
                    }
                ],
            }
        ],
    }


def snapshot_available_at(snapshots: tuple[OddsSnapshot, ...], match_id: str) -> datetime | None:
    eligible = [item.available_at for item in snapshots if item.match_id == match_id]
    return max(eligible) if eligible else None
