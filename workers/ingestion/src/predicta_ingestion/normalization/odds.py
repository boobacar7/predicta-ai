from __future__ import annotations

from decimal import Decimal
from typing import Any

from predicta_ingestion.canonical.enums import DataMode, SportCode
from predicta_ingestion.canonical.models import CanonicalBatch, OddsSelection, OddsSnapshot, Provenance
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import slugify, stable_entity_id
from predicta_ingestion.quality.freshness import classify_freshness
from predicta_ingestion.raw.store import StoredRaw

SELECTION_MAP = {
    "draw": "draw",
}


class OddsNormalizer:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def normalize(self, stored: StoredRaw, payload: dict[str, Any]) -> CanonicalBatch:
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValidationError("invalid_payload", "Odds payload data must be a list.")
        batch = CanonicalBatch()
        for event in data:
            if not isinstance(event, dict):
                raise ValidationError("invalid_payload", "Odds event must be an object.")
            self._add_event(batch, stored, event)
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
                raise ValidationError("invalid_payload", "Bookmaker must be an object.")
            last_update = parse_rfc3339(str(book["last_update"]))
            markets = book.get("markets")
            if not isinstance(markets, list):
                raise ValidationError("invalid_payload", "Markets must be a list.")
            for market in markets:
                if not isinstance(market, dict):
                    raise ValidationError("invalid_payload", "Market must be an object.")
                selections: list[OddsSelection] = []
                outcomes = market.get("outcomes")
                if not isinstance(outcomes, list) or not outcomes:
                    raise ValidationError("invalid_odds", "Odds market has no outcomes.")
                for outcome in outcomes:
                    if not isinstance(outcome, dict):
                        raise ValidationError("invalid_odds", "Outcome must be an object.")
                    price = Decimal(str(outcome["price"]))
                    if price <= 1:
                        raise ValidationError("invalid_odds", "Decimal odds must be strictly greater than 1.")
                    name = str(outcome["name"])
                    selection = SELECTION_MAP.get(name.lower(), slugify(name))
                    selections.append(OddsSelection(selection=selection, label=name, decimal_odds=price))
                batch.odds.append(
                    OddsSnapshot(
                        id=stable_entity_id(
                            "odds",
                            stored.envelope.provider,
                            str(book["key"]),
                            provider_match_id,
                            str(market["key"]),
                            last_update.isoformat(),
                        ),
                        match_id=stable_entity_id("match", SportCode.FOOTBALL.value, provider_match_id),
                        market=str(market["key"]),
                        bookmaker=str(book["key"]),
                        selections=selections,
                        match_natural_key=match_natural_key,
                        provenance=Provenance(
                            provider=stored.envelope.provider,
                            provider_id=f"{event['id']}:{book['key']}:{market['key']}:{last_update.isoformat()}",
                            collected_at=stored.envelope.collected_at,
                            available_at=last_update,
                            event_at=commence,
                            source=stored.envelope.provider,
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
