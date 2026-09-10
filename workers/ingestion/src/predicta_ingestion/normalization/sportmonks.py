from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from predicta_ingestion.canonical.enums import DataMode, MatchStatus, SportCode
from predicta_ingestion.canonical.models import CanonicalBatch, League, Match, Provenance, Sport, Team
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import slugify, stable_entity_id
from predicta_ingestion.providers.leagues import V1_LEAGUE_BY_SPORTMONKS_ID
from predicta_ingestion.quality.freshness import classify_freshness
from predicta_ingestion.quality.quarantine import QuarantineItem
from predicta_ingestion.raw.store import StoredRaw

# Finished results become PIT-visible only after kickoff plus this lag.
FINISHED_AVAILABLE_AFTER = timedelta(hours=3)

SPORTMONKS_STATUS: dict[int, MatchStatus] = {
    1: MatchStatus.SCHEDULED,  # NS
    2: MatchStatus.LIVE,  # INPLAY_1ST_HALF
    3: MatchStatus.LIVE,  # HT
    4: MatchStatus.LIVE,  # BREAK
    5: MatchStatus.FINISHED,  # FT
    6: MatchStatus.LIVE,  # INPLAY_ET
    7: MatchStatus.FINISHED,  # AET
    8: MatchStatus.FINISHED,  # FT_PEN
    9: MatchStatus.LIVE,  # INPLAY_PENALTIES
    10: MatchStatus.POSTPONED,
    11: MatchStatus.LIVE,  # SUSPENDED
    12: MatchStatus.CANCELLED,
    13: MatchStatus.SCHEDULED,  # TBA
    14: MatchStatus.FINISHED,  # WO
    15: MatchStatus.POSTPONED,  # ABANDONED
    16: MatchStatus.SCHEDULED,  # DELAYED
    17: MatchStatus.FINISHED,  # AWARDED
    18: MatchStatus.LIVE,  # INTERRUPTED
    19: MatchStatus.SCHEDULED,  # AWAITING_UPDATES
    20: MatchStatus.CANCELLED,  # DELETED
    21: MatchStatus.LIVE,  # EXTRA_TIME_BREAK
    22: MatchStatus.LIVE,  # INPLAY_2ND_HALF
    25: MatchStatus.LIVE,  # PEN_BREAK
    26: MatchStatus.SCHEDULED,  # PENDING
}


def parse_sportmonks_datetime(value: object) -> datetime:
    if value is None or value == "":
        raise ValidationError("naive_datetime", "Missing Sportmonks datetime.")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=UTC)
    text = str(value).strip().replace(" UTC", "Z")
    if text.endswith("Z") or (len(text) > 10 and ("+" in text[10:] or text.count("-") > 2)):
        if "T" not in text and " " in text:
            text = text.replace(" ", "T")
        return parse_rfc3339(text)
    if "T" not in text:
        text = text.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("naive_datetime", f"Unparseable Sportmonks datetime '{value}'.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class SportmonksFootballNormalizer:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self.quarantined: list[QuarantineItem] = []

    def normalize(self, stored: StoredRaw, payload: dict[str, Any]) -> CanonicalBatch:
        self.quarantined = []
        sport = Sport(
            id=stable_entity_id("sport", SportCode.FOOTBALL.value),
            code=SportCode.FOOTBALL,
            name="Football",
            provenance=self._provenance(stored, provider_id="1", event_at=None),
        )
        batch = CanonicalBatch(sports=[sport])
        data = payload.get("data")
        if isinstance(data, dict):
            self._add_league(batch, stored, sport, data)
            return batch
        if not isinstance(data, list):
            raise ValidationError("invalid_payload", "Sportmonks payload data must be an object or a list.")
        for item in data:
            if not isinstance(item, dict):
                self.quarantined.append(
                    self._quarantine(stored, "invalid_payload", "Expected a fixture object.", provider_entity_id=None)
                )
                continue
            try:
                self._add_fixture(batch, stored, sport, item)
            except ValidationError as exc:
                self.quarantined.append(
                    self._quarantine(
                        stored,
                        exc.reason_code,
                        exc.detail,
                        provider_entity_id=str(item.get("id")) if item.get("id") is not None else None,
                    )
                )
        return batch

    def _quarantine(
        self,
        stored: StoredRaw,
        reason_code: str,
        detail: str,
        *,
        provider_entity_id: str | None,
    ) -> QuarantineItem:
        return QuarantineItem(
            reason_code=reason_code,
            detail=detail,
            provider=stored.envelope.provider,
            entity_type="match",
            data_mode=stored.envelope.data_mode if isinstance(stored.envelope.data_mode, DataMode) else DataMode.LIVE,
            provider_entity_id=provider_entity_id,
            raw_payload_id=stored.id,
            created_at=self._clock.now(),
        )

    def _provenance(
        self,
        stored: StoredRaw,
        *,
        provider_id: str,
        event_at: datetime | None,
        terminal: bool = False,
        available_at: datetime | None = None,
    ) -> Provenance:
        available = available_at or stored.envelope.collected_at
        return Provenance(
            provider=stored.envelope.provider,
            provider_id=provider_id,
            collected_at=stored.envelope.collected_at,
            available_at=available,
            event_at=event_at,
            source=stored.envelope.provider,
            data_mode=stored.envelope.data_mode,
            freshness=classify_freshness(
                stored.envelope.resource,
                available_at=available,
                clock=self._clock,
                terminal=terminal,
            ),
            raw_payload_id=stored.id,
        )

    def _add_league(self, batch: CanonicalBatch, stored: StoredRaw, sport: Sport, raw: dict[str, Any]) -> League:
        provider_id = _provider_id(raw.get("id"), field="league")
        season = _season_name(raw)
        catalog = V1_LEAGUE_BY_SPORTMONKS_ID.get(int(provider_id))
        country_raw = raw.get("country")
        country_name = None
        if isinstance(country_raw, dict) and country_raw.get("name"):
            country_name = str(country_raw["name"])
        league = League(
            id=stable_entity_id("league", SportCode.FOOTBALL.value, "sportmonks", provider_id, season),
            sport_id=sport.id,
            name=str(raw.get("name") or (catalog.name if catalog else "")),
            country=country_name or (catalog.country if catalog else "Unknown"),
            season=season,
            tier=1,
            provenance=self._provenance(stored, provider_id=provider_id, event_at=None),
        )
        if not league.name:
            raise ValidationError("invalid_payload", "League name is missing.")
        batch.leagues.append(league)
        return league

    def _add_fixture(self, batch: CanonicalBatch, stored: StoredRaw, sport: Sport, raw: dict[str, Any]) -> None:
        if raw.get("placeholder") is True:
            raise ValidationError("placeholder_fixture", "Placeholder Sportmonks fixtures are quarantined.")
        fixture_id = _provider_id(raw.get("id"), field="fixture")
        state = raw.get("state") if isinstance(raw.get("state"), dict) else {}
        state_id = raw.get("state_id")
        if state_id is None and isinstance(state, dict):
            state_id = state.get("id")
        if state_id is None:
            raise ValidationError("unknown_status", "Unmapped Sportmonks state_id 'None'.")
        try:
            status = SPORTMONKS_STATUS[int(str(state_id))]
        except (TypeError, ValueError, KeyError) as exc:
            raise ValidationError("unknown_status", f"Unmapped Sportmonks state_id '{state_id}'.") from exc
        kickoff = parse_sportmonks_datetime(raw.get("starting_at") or raw.get("starting_at_timestamp"))
        league_raw: dict[str, Any]
        if isinstance(raw.get("league"), dict):
            league_raw = raw["league"]
        else:
            league_raw = {"id": raw.get("league_id")}
        if isinstance(raw.get("season"), dict):
            league_raw = {**league_raw, "season": raw["season"]}
        league = self._league_from_fixture(batch, stored, sport, league_raw, raw.get("league_id"))
        home, away = self._participants(raw)
        home_team = self._team(stored, sport, league, home)
        away_team = self._team(stored, sport, league, away)
        if home_team.id == away_team.id:
            raise ValidationError("same_team", "Home team and away team must be different.")
        if league.season == "unknown":
            raise ValidationError("missing_season", "Fixture season is missing.")
        home_score, away_score = _final_scores(raw, status)
        if home_score is not None and home_score < 0:
            raise ValidationError("inconsistent_score", "Home score cannot be negative.")
        if away_score is not None and away_score < 0:
            raise ValidationError("inconsistent_score", "Away score cannot be negative.")
        venue_raw: dict[str, Any] = raw["venue"] if isinstance(raw.get("venue"), dict) else {}
        venue = str(venue_raw.get("name") or "") or None
        available_at = _match_available_at(status=status, kickoff=kickoff, collected_at=stored.envelope.collected_at)
        match = Match(
            id=stable_entity_id("match", SportCode.FOOTBALL.value, "sportmonks", fixture_id),
            sport_id=sport.id,
            league_id=league.id,
            kickoff_at=kickoff,
            status=status,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            venue=venue,
            home_score=home_score,
            away_score=away_score,
            natural_key=(
                f"{SportCode.FOOTBALL.value}|{slugify(home_team.name)}|{slugify(away_team.name)}|{kickoff.isoformat()}"
            ),
            provenance=self._provenance(
                stored,
                provider_id=fixture_id,
                event_at=kickoff,
                terminal=status is MatchStatus.FINISHED,
                available_at=available_at,
            ),
        )
        batch.leagues.append(league)
        batch.teams.extend([home_team, away_team])
        batch.matches.append(match)

    def _league_from_fixture(
        self,
        batch: CanonicalBatch,
        stored: StoredRaw,
        sport: Sport,
        league_raw: dict[str, Any],
        league_id: object,
    ) -> League:
        if "id" not in league_raw or league_raw.get("id") is None:
            league_raw = {**league_raw, "id": league_id}
        return self._add_league(batch, stored, sport, league_raw)

    def _team(self, stored: StoredRaw, sport: Sport, league: League, raw: dict[str, Any]) -> Team:
        provider_id = _provider_id(raw.get("id"), field="team")
        name = str(raw.get("name") or "")
        if not name:
            raise ValidationError("invalid_payload", "Team name is missing.")
        short = str(raw.get("short_code") or raw.get("short_name") or name[:3]).upper()[:12]
        return Team(
            id=stable_entity_id("team", SportCode.FOOTBALL.value, "sportmonks", provider_id),
            sport_id=sport.id,
            league_id=league.id,
            name=name,
            short_name=str(raw.get("short_name") or name),
            abbreviation=short,
            provenance=self._provenance(stored, provider_id=provider_id, event_at=None),
        )

    def _participants(self, raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        participants = raw.get("participants")
        if not isinstance(participants, list) or len(participants) < 2:
            raise ValidationError("missing_provider_id", "Fixture participants are missing.")
        home = _participant_by_location(participants, "home")
        away = _participant_by_location(participants, "away")
        return home, away


def _match_available_at(*, status: MatchStatus, kickoff: datetime, collected_at: datetime) -> datetime:
    if status is MatchStatus.FINISHED:
        assumed = kickoff + FINISHED_AVAILABLE_AFTER
        available = min(collected_at, assumed)
        if available <= kickoff:
            return kickoff + timedelta(minutes=90)
        return available
    return collected_at


def _final_scores(raw: dict[str, Any], status: MatchStatus) -> tuple[int | None, int | None]:
    if status not in {MatchStatus.FINISHED, MatchStatus.LIVE}:
        return None, None
    scores = raw.get("scores")
    if not isinstance(scores, list):
        if status is MatchStatus.FINISHED:
            raise ValidationError(
                "invalid_payload",
                "Finished fixtures must include scores; missing scores are not zero.",
            )
        return None, None
    home = _score_for(scores, "home")
    away = _score_for(scores, "away")
    if status is MatchStatus.FINISHED and (home is None or away is None):
        raise ValidationError(
            "invalid_payload",
            "Finished fixtures must include scores; missing scores are not zero.",
        )
    return home, away


def _score_for(scores: list[Any], location: str) -> int | None:
    current: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    for item in scores:
        if not isinstance(item, dict):
            continue
        payload: dict[str, Any] = item["score"] if isinstance(item.get("score"), dict) else {}
        participant = str(payload.get("participant") or "").lower()
        if participant != location:
            continue
        description = str(item.get("description") or "").upper()
        if description == "CURRENT":
            current.append(item)
        elif description in {"2ND_HALF", "FULLTIME", "FULL_TIME", "FT"}:
            fallback.append(item)
    chosen = (current or fallback)
    if not chosen:
        return None
    goals = chosen[0].get("score", {}).get("goals") if isinstance(chosen[0].get("score"), dict) else None
    if goals is None:
        return None
    return int(goals)


def _participant_by_location(participants: list[Any], location: str) -> dict[str, Any]:
    for item in participants:
        if not isinstance(item, dict):
            continue
        meta: dict[str, Any] = item["meta"] if isinstance(item.get("meta"), dict) else {}
        if str(meta.get("location") or "").lower() == location:
            return item
    raise ValidationError("missing_provider_id", f"Missing {location} participant.")


def _provider_id(value: object, *, field: str) -> str:
    if value is None or value == "":
        raise ValidationError("missing_provider_id", f"Missing provider id for {field}.")
    return str(value)


def _season_name(raw: dict[str, Any]) -> str:
    season = raw.get("season")
    if isinstance(season, dict) and season.get("name"):
        return str(season["name"])
    if raw.get("season_id") is not None:
        return str(raw["season_id"])
    return "unknown"
