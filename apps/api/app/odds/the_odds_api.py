from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.odds.exceptions import OddsUnavailableError
from app.odds.types import FOOTBALL_1X2_MARKET, DataMode, Football1x2Selection, OddsSelection, OddsSnapshot

LIVE_ODDS_SOURCE = "the-odds-api-v4"
PROVIDER_H2H_MARKET = "h2h"
DRAW_NAMES = frozenset({"draw", "the draw"})


def football_1x2_selection(name: str, *, home_team: str, away_team: str) -> Football1x2Selection | None:
    if name == home_team:
        return Football1x2Selection.HOME
    if name == away_team:
        return Football1x2Selection.AWAY
    if name.lower() in DRAW_NAMES:
        return Football1x2Selection.DRAW
    return None


def map_the_odds_api_events(
    events: list[dict[str, Any]],
    *,
    match_id: str,
    market: str,
    source: str = LIVE_ODDS_SOURCE,
    data_mode: DataMode = "live",
    raw_payload_id: str | None = None,
) -> tuple[OddsSnapshot, ...]:
    if market != FOOTBALL_1X2_MARKET:
        raise OddsUnavailableError(f"Unsupported odds market: {market}.")
    snapshots: list[OddsSnapshot] = []
    for event in events:
        snapshots.extend(
            _map_event(
                event,
                match_id=match_id,
                source=source,
                data_mode=data_mode,
                raw_payload_id=raw_payload_id,
            )
        )
    return tuple(snapshots)


def _map_event(
    event: dict[str, Any],
    *,
    match_id: str,
    source: str,
    data_mode: DataMode,
    raw_payload_id: str | None,
) -> tuple[OddsSnapshot, ...]:
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    event_id = str(event.get("id") or "")
    if not home or not away or not event_id:
        raise OddsUnavailableError("Live odds event is missing id or team names; values are never invented.")
    bookmakers = event.get("bookmakers")
    if not isinstance(bookmakers, list):
        raise OddsUnavailableError("Live odds bookmakers must be a list.")
    snapshots: list[OddsSnapshot] = []
    for book in bookmakers:
        if not isinstance(book, dict):
            continue
        mapped = _map_bookmaker(
            book,
            event_id=event_id,
            match_id=match_id,
            home=home,
            away=away,
            source=source,
            data_mode=data_mode,
            raw_payload_id=raw_payload_id,
        )
        if mapped is not None:
            snapshots.append(mapped)
    return tuple(snapshots)


def _map_bookmaker(
    book: dict[str, Any],
    *,
    event_id: str,
    match_id: str,
    home: str,
    away: str,
    source: str,
    data_mode: DataMode,
    raw_payload_id: str | None,
) -> OddsSnapshot | None:
    book_key = str(book.get("key") or "")
    last_update_raw = book.get("last_update")
    if not book_key or not last_update_raw:
        return None
    last_update = _require_aware(last_update_raw)
    markets = book.get("markets")
    if not isinstance(markets, list):
        return None
    for market in markets:
        if not isinstance(market, dict) or str(market.get("key") or "") != PROVIDER_H2H_MARKET:
            continue
        selections = _map_h2h_selections(market, home=home, away=away)
        if not selections:
            return None
        provider_id = f"{event_id}:{book_key}:{FOOTBALL_1X2_MARKET}:{last_update.isoformat()}"
        return OddsSnapshot(
            id=f"odd_{event_id}_{book_key}_{FOOTBALL_1X2_MARKET}_{last_update.strftime('%Y%m%dT%H%M%S')}",
            provider_id=provider_id,
            match_id=match_id,
            bookmaker=book_key,
            market=FOOTBALL_1X2_MARKET,
            selections=selections,
            collected_at=last_update,
            available_at=last_update,
            source=source,
            data_mode=data_mode,
            raw_payload_id=raw_payload_id,
        )
    return None


def _map_h2h_selections(market: dict[str, Any], *, home: str, away: str) -> tuple[OddsSelection, ...]:
    outcomes = market.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        return ()
    mapped: list[OddsSelection] = []
    seen: set[Football1x2Selection] = set()
    for outcome in outcomes:
        if not isinstance(outcome, dict) or "price" not in outcome:
            return ()
        try:
            price = Decimal(str(outcome["price"]))
        except InvalidOperation:
            return ()
        if price <= 1:
            return ()
        selection = football_1x2_selection(str(outcome.get("name") or ""), home_team=home, away_team=away)
        if selection is None:
            continue
        if selection in seen:
            return ()
        seen.add(selection)
        mapped.append(OddsSelection(selection, price))
    return tuple(mapped)


def _require_aware(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OddsUnavailableError("Live odds timestamps must include a timezone.")
    return parsed
