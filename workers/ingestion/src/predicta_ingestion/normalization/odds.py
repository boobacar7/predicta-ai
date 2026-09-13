from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from predicta_ingestion.canonical.enums import DataMode, SportCode
from predicta_ingestion.canonical.models import CanonicalBatch, OddsSelection, OddsSnapshot, Provenance
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import slugify, stable_entity_id
from predicta_ingestion.providers.the_odds_api import LIVE_ODDS_PROVIDER, LIVE_ODDS_SOURCE
from predicta_ingestion.quality.freshness import classify_freshness
from predicta_ingestion.quality.quarantine import QuarantineItem
from predicta_ingestion.raw.store import StoredRaw

CANONICAL_1X2_MARKET = "1X2"
PROVIDER_H2H_MARKET = "h2h"
DRAW_NAMES = frozenset({"draw", "the draw"})
HOME_SELECTION = "HOME"
DRAW_SELECTION = "DRAW"
AWAY_SELECTION = "AWAY"


def canonical_odds_source(provider: str) -> str:
    if provider == LIVE_ODDS_PROVIDER:
        return LIVE_ODDS_SOURCE
    return provider


def football_1x2_selection(name: str, *, home_team: str, away_team: str) -> str | None:
    """Map a The Odds API h2h outcome name. Unknown names are not guessed."""
    if name == home_team:
        return HOME_SELECTION
    if name == away_team:
        return AWAY_SELECTION
    if name.lower() in DRAW_NAMES:
        return DRAW_SELECTION
    return None


class OddsNormalizer:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self.quarantined: list[QuarantineItem] = []

    def normalize(self, stored: StoredRaw, payload: dict[str, Any]) -> CanonicalBatch:
        self.quarantined = []
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValidationError("invalid_payload", "Odds payload data must be a list.")
        batch = CanonicalBatch()
        for event in data:
            if not isinstance(event, dict):
                self.quarantined.append(
                    self._quarantine(stored, "invalid_payload", "Odds event must be an object.")
                )
                continue
            try:
                self._add_event(batch, stored, event)
            except ValidationError as exc:
                self.quarantined.append(
                    self._quarantine(
                        stored,
                        exc.reason_code,
                        exc.detail,
                        provider_entity_id=str(event.get("id")) if event.get("id") is not None else None,
                    )
                )
        return batch

    def _add_event(self, batch: CanonicalBatch, stored: StoredRaw, event: dict[str, Any]) -> None:
        commence = parse_rfc3339(str(event["commence_time"]))
        home = str(event["home_team"])
        away = str(event["away_team"])
        provider_match_id = str(event.get("provider_match_id") or event["id"])
        match_natural_key = f"{SportCode.FOOTBALL.value}|{slugify(home)}|{slugify(away)}|{commence.isoformat()}"
        bookmakers = event.get("bookmakers")
        if not isinstance(bookmakers, list):
            raise ValidationError("invalid_payload", "Odds bookmakers must be a list.")
        for book in bookmakers:
            if not isinstance(book, dict):
                self.quarantined.append(
                    self._quarantine(stored, "invalid_payload", "Bookmaker must be an object.", provider_match_id)
                )
                continue
            self._add_bookmaker(
                batch,
                stored,
                event_id=str(event["id"]),
                provider_match_id=provider_match_id,
                match_natural_key=match_natural_key,
                commence=commence,
                home=home,
                away=away,
                book=book,
            )

    def _add_bookmaker(
        self,
        batch: CanonicalBatch,
        stored: StoredRaw,
        *,
        event_id: str,
        provider_match_id: str,
        match_natural_key: str,
        commence: datetime,
        home: str,
        away: str,
        book: dict[str, Any],
    ) -> None:
        book_key = str(book.get("key") or "")
        if not book_key:
            self.quarantined.append(
                self._quarantine(stored, "invalid_payload", "Bookmaker key is missing.", provider_match_id)
            )
            return
        last_update_raw = book.get("last_update")
        if not last_update_raw:
            self.quarantined.append(
                self._quarantine(
                    stored,
                    "missing_timestamp",
                    "Bookmaker last_update is missing; availability is never invented.",
                    f"{provider_match_id}:{book_key}",
                )
            )
            return
        last_update = parse_rfc3339(str(last_update_raw))
        markets = book.get("markets")
        if not isinstance(markets, list):
            self.quarantined.append(
                self._quarantine(
                    stored,
                    "invalid_payload",
                    "Markets must be a list.",
                    f"{provider_match_id}:{book_key}",
                )
            )
            return
        for market in markets:
            if not isinstance(market, dict):
                self.quarantined.append(
                    self._quarantine(
                        stored,
                        "invalid_payload",
                        "Market must be an object.",
                        f"{provider_match_id}:{book_key}",
                    )
                )
                continue
            market_key = str(market.get("key") or "")
            if market_key != PROVIDER_H2H_MARKET:
                continue
            try:
                selections = self._h2h_selections(market, home=home, away=away)
            except ValidationError as exc:
                self.quarantined.append(
                    self._quarantine(
                        stored,
                        exc.reason_code,
                        exc.detail,
                        f"{provider_match_id}:{book_key}:{market_key}",
                    )
                )
                continue
            if not selections:
                self.quarantined.append(
                    self._quarantine(
                        stored,
                        "invalid_odds",
                        "Football 1X2 market has no mappable outcomes.",
                        f"{provider_match_id}:{book_key}:{market_key}",
                    )
                )
                continue
            batch.odds.append(
                OddsSnapshot(
                    id=stable_entity_id(
                        "odds",
                        stored.envelope.provider,
                        book_key,
                        provider_match_id,
                        CANONICAL_1X2_MARKET,
                        last_update.isoformat(),
                    ),
                    match_id=stable_entity_id("match", SportCode.FOOTBALL.value, provider_match_id),
                    market=CANONICAL_1X2_MARKET,
                    bookmaker=book_key,
                    selections=selections,
                    match_natural_key=match_natural_key,
                    provenance=Provenance(
                        provider=stored.envelope.provider,
                        provider_id=f"{event_id}:{book_key}:{CANONICAL_1X2_MARKET}:{last_update.isoformat()}",
                        collected_at=last_update,
                        available_at=last_update,
                        event_at=commence,
                        source=canonical_odds_source(stored.envelope.provider),
                        data_mode=DataMode(stored.envelope.data_mode),
                        freshness=classify_freshness(
                            stored.envelope.resource,
                            available_at=last_update,
                            clock=self._clock,
                        ),
                        raw_payload_id=stored.id,
                    ),
                )
            )

    def _h2h_selections(self, market: dict[str, Any], *, home: str, away: str) -> list[OddsSelection]:
        outcomes = market.get("outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            raise ValidationError("invalid_odds", "Odds market has no outcomes.")
        selections: list[OddsSelection] = []
        seen: set[str] = set()
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                raise ValidationError("invalid_odds", "Outcome must be an object.")
            if "price" not in outcome:
                raise ValidationError("invalid_odds", "Outcome price is missing; odds are never invented.")
            try:
                price = Decimal(str(outcome["price"]))
            except InvalidOperation as exc:
                raise ValidationError("invalid_odds", "Decimal odds must be a finite number greater than 1.") from exc
            if price <= 1:
                raise ValidationError("invalid_odds", "Decimal odds must be strictly greater than 1.")
            name = str(outcome.get("name") or "")
            selection = football_1x2_selection(name, home_team=home, away_team=away)
            if selection is None:
                continue
            if selection in seen:
                raise ValidationError("invalid_odds", "Odds snapshot contains duplicate selections.")
            seen.add(selection)
            selections.append(OddsSelection(selection=selection, label=name, decimal_odds=price))
        return selections

    def _quarantine(
        self,
        stored: StoredRaw,
        reason_code: str,
        detail: str,
        provider_entity_id: str | None = None,
    ) -> QuarantineItem:
        return QuarantineItem(
            reason_code=reason_code,
            detail=detail,
            provider=stored.envelope.provider,
            entity_type="odds_snapshot",
            data_mode=DataMode(stored.envelope.data_mode),
            provider_entity_id=provider_entity_id,
            raw_payload_id=stored.id,
            created_at=self._clock.now(),
        )
