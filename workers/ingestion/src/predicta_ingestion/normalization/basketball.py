from __future__ import annotations

from typing import Any

from predicta_ingestion.canonical.enums import DataMode, MatchStatus, SportCode
from predicta_ingestion.canonical.models import CanonicalBatch, League, Match, Provenance, Sport, Team
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import slugify, stable_entity_id
from predicta_ingestion.quality.freshness import classify_freshness
from predicta_ingestion.raw.store import StoredRaw

BASKETBALL_STATUS = {
    "Final": MatchStatus.FINISHED,
    "Scheduled": MatchStatus.SCHEDULED,
}


class BasketballNormalizer:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def normalize(self, stored: StoredRaw, payload: dict[str, Any]) -> CanonicalBatch:
        sport = Sport(
            id=stable_entity_id("sport", SportCode.BASKETBALL.value),
            code=SportCode.BASKETBALL,
            name="Basketball",
            provenance=_prov(stored, self._clock, SportCode.BASKETBALL.value),
        )
        batch = CanonicalBatch(sports=[sport])
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValidationError("invalid_payload", "Basketball payload data must be a list.")
        for raw in data:
            if not isinstance(raw, dict):
                raise ValidationError("invalid_payload", "Basketball game must be an object.")
            self._add_game(batch, stored, sport, raw)
        return batch

    def _add_game(self, batch: CanonicalBatch, stored: StoredRaw, sport: Sport, raw: dict[str, Any]) -> None:
        status_key = str(raw.get("status"))
        if status_key not in BASKETBALL_STATUS:
            raise ValidationError("unknown_status", f"Unmapped basketball status '{status_key}'.")
        league_raw = raw.get("league")
        if not isinstance(league_raw, dict):
            raise ValidationError("invalid_payload", "Missing basketball league.")
        kickoff = parse_rfc3339(str(raw["date"]))
        season = str(league_raw["season"])
        league = League(
            id=stable_entity_id("league", SportCode.BASKETBALL.value, str(league_raw["name"]), season),
            sport_id=sport.id,
            name=str(league_raw["name"]),
            country=str(league_raw["country"]),
            season=season,
            provenance=_prov(stored, self._clock, str(league_raw["id"])),
        )
        home_raw = raw["home_team"]
        away_raw = raw["visitor_team"]
        if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
            raise ValidationError("invalid_payload", "Basketball teams must be objects.")
        home = _team(stored, self._clock, sport, league, home_raw)
        away = _team(stored, self._clock, sport, league, away_raw)
        status = BASKETBALL_STATUS[status_key]
        batch.leagues.append(league)
        batch.teams.extend([home, away])
        batch.matches.append(
            Match(
                id=stable_entity_id("match", SportCode.BASKETBALL.value, str(raw["id"])),
                sport_id=sport.id,
                league_id=league.id,
                kickoff_at=kickoff,
                status=status,
                home_team_id=home.id,
                away_team_id=away.id,
                home_score=int(raw["home_team_score"]) if raw.get("home_team_score") is not None else None,
                away_score=int(raw["visitor_team_score"]) if raw.get("visitor_team_score") is not None else None,
                natural_key=f"{SportCode.BASKETBALL.value}|{slugify(home.name)}|{slugify(away.name)}|{kickoff.isoformat()}",
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


def _team(stored: StoredRaw, clock: Clock, sport: Sport, league: League, raw: dict[str, Any]) -> Team:
    name = str(raw["full_name"])
    return Team(
        id=stable_entity_id("team", SportCode.BASKETBALL.value, name, league.id),
        sport_id=sport.id,
        league_id=league.id,
        name=name,
        short_name=name,
        abbreviation=str(raw.get("abbreviation") or name[:3])[:12],
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
