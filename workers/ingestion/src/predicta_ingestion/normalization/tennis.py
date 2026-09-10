from __future__ import annotations

from typing import Any

from predicta_ingestion.canonical.enums import DataMode, MatchStatus, SportCode
from predicta_ingestion.canonical.models import CanonicalBatch, League, Match, Player, Provenance, Sport
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import slugify, stable_entity_id
from predicta_ingestion.quality.freshness import classify_freshness
from predicta_ingestion.raw.store import StoredRaw

TENNIS_STATUS = {
    "finished": MatchStatus.FINISHED,
    "scheduled": MatchStatus.SCHEDULED,
    "live": MatchStatus.LIVE,
}


class TennisNormalizer:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def normalize(self, stored: StoredRaw, payload: dict[str, Any]) -> CanonicalBatch:
        sport = Sport(
            id=stable_entity_id("sport", SportCode.TENNIS.value),
            code=SportCode.TENNIS,
            name="Tennis",
            provenance=_prov(stored, self._clock, SportCode.TENNIS.value),
        )
        batch = CanonicalBatch(sports=[sport])
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValidationError("invalid_payload", "Tennis payload items must be a list.")
        for raw in items:
            if not isinstance(raw, dict):
                raise ValidationError("invalid_payload", "Tennis match must be an object.")
            self._add_match(batch, stored, sport, raw)
        return batch

    def _add_match(self, batch: CanonicalBatch, stored: StoredRaw, sport: Sport, raw: dict[str, Any]) -> None:
        status_key = str(raw.get("status"))
        if status_key not in TENNIS_STATUS:
            raise ValidationError("unknown_status", f"Unmapped tennis status '{status_key}'.")
        tournament = raw.get("tournament")
        if not isinstance(tournament, dict):
            raise ValidationError("invalid_payload", "Missing tennis tournament.")
        home_raw = raw.get("home_player")
        away_raw = raw.get("away_player")
        if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
            raise ValidationError("invalid_payload", "Tennis players must be objects.")
        kickoff = parse_rfc3339(str(raw["kickoff"]))
        season = str(tournament["season"])
        league = League(
            id=stable_entity_id("league", SportCode.TENNIS.value, str(tournament["name"]), season),
            sport_id=sport.id,
            name=str(tournament["name"]),
            country=str(tournament["country"]),
            season=season,
            provenance=_prov(stored, self._clock, str(tournament["id"])),
        )
        home = _player(stored, self._clock, sport, home_raw)
        away = _player(stored, self._clock, sport, away_raw)
        status = TENNIS_STATUS[status_key]
        batch.leagues.append(league)
        batch.players.extend([home, away])
        batch.matches.append(
            Match(
                id=stable_entity_id("match", SportCode.TENNIS.value, str(raw["id"])),
                sport_id=sport.id,
                league_id=league.id,
                kickoff_at=kickoff,
                status=status,
                home_player_id=home.id,
                away_player_id=away.id,
                home_score=int(raw["home_score"]) if raw.get("home_score") is not None else None,
                away_score=int(raw["away_score"]) if raw.get("away_score") is not None else None,
                surface=str(raw["surface"]) if raw.get("surface") else None,
                natural_key=f"{SportCode.TENNIS.value}|{slugify(home.name)}|{slugify(away.name)}|{kickoff.isoformat()}",
                provenance=_prov(
                    stored,
                    self._clock,
                    str(raw["id"]),
                    event_at=kickoff,
                    terminal=status is MatchStatus.FINISHED,
                    available_at=kickoff if status is MatchStatus.FINISHED else stored.envelope.collected_at,
                ),
            )
        )


def _player(stored: StoredRaw, clock: Clock, sport: Sport, raw: dict[str, Any]) -> Player:
    name = str(raw["name"])
    return Player(
        id=stable_entity_id("player", SportCode.TENNIS.value, name, str(raw["id"])),
        sport_id=sport.id,
        name=name,
        country=str(raw.get("country") or "Unknown"),
        provenance=_prov(stored, clock, str(raw["id"])),
    )


def _prov(
    stored: StoredRaw,
    clock: Clock,
    provider_id: str,
    *,
    event_at: Any = None,
    terminal: bool = False,
    available_at: Any = None,
) -> Provenance:
    available = available_at or stored.envelope.collected_at
    return Provenance(
        provider=stored.envelope.provider,
        provider_id=provider_id,
        collected_at=stored.envelope.collected_at,
        available_at=available,
        event_at=event_at,
        source=stored.envelope.provider,
        data_mode=DataMode(stored.envelope.data_mode),
        freshness=classify_freshness(stored.envelope.resource, available_at=available, clock=clock, terminal=terminal),
        raw_payload_id=stored.id,
    )
