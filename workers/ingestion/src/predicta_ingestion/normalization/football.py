from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from predicta_ingestion.canonical.enums import (
    Availability,
    DataMode,
    InjuryStatus,
    LineupRole,
    MatchStatus,
    SportCode,
)
from predicta_ingestion.canonical.models import (
    CanonicalBatch,
    Injury,
    League,
    Lineup,
    LineupPlayer,
    Match,
    MatchEvent,
    Player,
    Provenance,
    Sport,
    StandingSnapshot,
    Team,
    TeamStats,
)
from predicta_ingestion.clock import Clock, parse_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.ids import slugify, stable_entity_id
from predicta_ingestion.quality.freshness import classify_freshness
from predicta_ingestion.raw.store import StoredRaw

FOOTBALL_STATUS = {
    "NS": MatchStatus.SCHEDULED,
    "TBD": MatchStatus.SCHEDULED,
    "1H": MatchStatus.LIVE,
    "2H": MatchStatus.LIVE,
    "HT": MatchStatus.LIVE,
    "LIVE": MatchStatus.LIVE,
    "FT": MatchStatus.FINISHED,
    "AET": MatchStatus.FINISHED,
    "PEN": MatchStatus.FINISHED,
    "PST": MatchStatus.POSTPONED,
    "CANC": MatchStatus.CANCELLED,
}


def _as_dict(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("invalid_payload", f"Expected object for {field}.")
    return value


def _as_list(value: object) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("invalid_payload", "Expected a list.")
    return value


def _provider_id(value: object, *, field: str) -> str:
    if value is None or value == "":
        raise ValidationError("missing_provider_id", f"Missing provider id for {field}.")
    return str(value)


class FootballNormalizer:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def normalize(self, stored: StoredRaw, payload: dict[str, Any]) -> CanonicalBatch:
        sport = Sport(
            id=stable_entity_id("sport", SportCode.FOOTBALL.value),
            code=SportCode.FOOTBALL,
            name="Football",
            provenance=self._provenance(stored, provider_id=SportCode.FOOTBALL.value, event_at=None),
        )
        batch = CanonicalBatch(sports=[sport])
        for item in _as_list(payload.get("response")):
            self._add_fixture(batch, stored, sport, _as_dict(item, field="fixture"))
        for standing in _as_list(payload.get("standings")):
            self._add_standing(batch, stored, sport, _as_dict(standing, field="standing"))
        for injury in _as_list(payload.get("injuries")):
            self._add_injury(batch, stored, sport, _as_dict(injury, field="injury"))
        return batch

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
        resource = stored.envelope.resource
        return Provenance(
            provider=stored.envelope.provider,
            provider_id=provider_id,
            collected_at=stored.envelope.collected_at,
            available_at=available,
            event_at=event_at,
            source=stored.envelope.provider,
            data_mode=DataMode.MOCK if stored.envelope.data_mode is DataMode.MOCK else stored.envelope.data_mode,
            freshness=classify_freshness(resource, available_at=available, clock=self._clock, terminal=terminal),
            raw_payload_id=stored.id,
        )

    def _add_fixture(self, batch: CanonicalBatch, stored: StoredRaw, sport: Sport, item: dict[str, Any]) -> None:
        fixture = _as_dict(item.get("fixture"), field="fixture.fixture")
        league_raw = _as_dict(item.get("league"), field="league")
        teams = _as_dict(item.get("teams"), field="teams")
        home = _as_dict(teams.get("home"), field="teams.home")
        away = _as_dict(teams.get("away"), field="teams.away")
        status_raw = _as_dict(fixture.get("status"), field="status")
        short = str(status_raw.get("short", ""))
        if short not in FOOTBALL_STATUS:
            raise ValidationError("unknown_status", f"Unmapped fixture status '{short}'.")
        status = FOOTBALL_STATUS[short]
        kickoff = parse_rfc3339(str(fixture["date"]))
        season = str(league_raw.get("season"))
        league = League(
            id=stable_entity_id("league", SportCode.FOOTBALL.value, str(league_raw["name"]), season),
            sport_id=sport.id,
            name=str(league_raw["name"]),
            country=str(league_raw["country"]),
            season=season,
            tier=1,
            provenance=self._provenance(
                stored,
                provider_id=_provider_id(league_raw.get("id"), field="league"),
                event_at=None,
            ),
        )
        home_team = self._team(stored, sport, league, home)
        away_team = self._team(stored, sport, league, away)
        goals = _as_dict(item.get("goals") or {}, field="goals")
        home_score = goals.get("home")
        away_score = goals.get("away")
        match = Match(
            id=stable_entity_id("match", SportCode.FOOTBALL.value, _provider_id(fixture.get("id"), field="fixture")),
            sport_id=sport.id,
            league_id=league.id,
            kickoff_at=kickoff,
            status=status,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            venue=str(_as_dict(fixture.get("venue") or {}, field="venue").get("name") or "") or None,
            home_score=int(home_score) if home_score is not None else None,
            away_score=int(away_score) if away_score is not None else None,
            natural_key=f"{SportCode.FOOTBALL.value}|{slugify(home_team.name)}|{slugify(away_team.name)}|{kickoff.isoformat()}",
            provenance=self._provenance(
                stored,
                provider_id=_provider_id(fixture.get("id"), field="fixture"),
                event_at=kickoff,
                terminal=status is MatchStatus.FINISHED,
                available_at=kickoff if status is MatchStatus.FINISHED else stored.envelope.collected_at,
            ),
        )
        batch.leagues.append(league)
        batch.teams.extend([home_team, away_team])
        batch.matches.append(match)
        for event in _as_list(item.get("events")):
            self._add_event(batch, stored, match, event)
        for line in _as_list(item.get("lineups")):
            self._add_lineup(batch, stored, match, line)
        for stat_block in _as_list(item.get("statistics")):
            self._add_team_stats(batch, stored, match, league, stat_block)

    def _team(self, stored: StoredRaw, sport: Sport, league: League, raw: dict[str, Any]) -> Team:
        name = str(raw["name"])
        code = str(raw.get("code") or name[:3]).upper()[:12]
        return Team(
            id=stable_entity_id("team", SportCode.FOOTBALL.value, name, league.id),
            sport_id=sport.id,
            league_id=league.id,
            name=name,
            short_name=name,
            abbreviation=code,
            provenance=self._provenance(stored, provider_id=_provider_id(raw.get("id"), field="team"), event_at=None),
        )

    def _add_event(self, batch: CanonicalBatch, stored: StoredRaw, match: Match, raw: object) -> None:
        item = _as_dict(raw, field="event")
        player = _as_dict(item.get("player") or {}, field="event.player")
        team = _as_dict(item.get("team") or {}, field="event.team")
        elapsed = _as_dict(item.get("time") or {}, field="event.time").get("elapsed")
        provider_event_id = f"{match.provenance.provider_id}:{elapsed}:{player.get('id')}"
        player_id = None
        if player.get("id") is not None:
            player_obj = Player(
                id=stable_entity_id("player", SportCode.FOOTBALL.value, str(player.get("name")), str(player.get("id"))),
                sport_id=match.sport_id,
                name=str(player.get("name")),
                country="Mockland",
                provenance=self._provenance(
                    stored,
                    provider_id=_provider_id(player.get("id"), field="player"),
                    event_at=None,
                ),
            )
            batch.players.append(player_obj)
            player_id = player_obj.id
        team_id = None
        if team.get("id") is not None:
            team_id = next(
                (team_item.id for team_item in batch.teams if team_item.provenance.provider_id == str(team["id"])),
                None,
            )
        batch.events.append(
            MatchEvent(
                id=stable_entity_id("event", SportCode.FOOTBALL.value, provider_event_id),
                match_id=match.id,
                event_type=slugify(str(item.get("type"))),
                label=str(item.get("detail") or item.get("type")),
                minute=int(elapsed) if elapsed is not None else None,
                team_id=team_id,
                player_id=player_id,
                provenance=self._provenance(
                    stored,
                    provider_id=provider_event_id,
                    event_at=match.kickoff_at,
                    terminal=True,
                    available_at=match.kickoff_at,
                ),
            )
        )

    def _add_lineup(self, batch: CanonicalBatch, stored: StoredRaw, match: Match, raw: object) -> None:
        item = _as_dict(raw, field="lineup")
        team_raw = _as_dict(item.get("team"), field="lineup.team")
        team_id = next((team.id for team in batch.teams if team.provenance.provider_id == str(team_raw["id"])), None)
        if team_id is None:
            raise ValidationError("missing_provider_id", "Lineup team is not mapped.")
        players: list[LineupPlayer] = []
        for starter in _as_list(item.get("startXI")):
            players.append(self._lineup_player(batch, stored, match, starter, LineupRole.STARTER))
        for bench in _as_list(item.get("substitutes")):
            players.append(self._lineup_player(batch, stored, match, bench, LineupRole.BENCH))
        observed = match.kickoff_at - timedelta(minutes=60)
        batch.lineups.append(
            Lineup(
                id=stable_entity_id("lineup", match.id, team_id),
                match_id=match.id,
                team_id=team_id,
                availability=Availability.AVAILABLE,
                formation=str(item["formation"]) if item.get("formation") else None,
                players=players,
                provenance=self._provenance(
                    stored,
                    provider_id=f"{match.provenance.provider_id}:{team_raw['id']}",
                    event_at=observed,
                    available_at=observed,
                    terminal=True,
                ),
            )
        )

    def _lineup_player(
        self,
        batch: CanonicalBatch,
        stored: StoredRaw,
        match: Match,
        raw: object,
        role: LineupRole,
    ) -> LineupPlayer:
        wrapper = _as_dict(raw, field="lineup.player")
        player = _as_dict(wrapper.get("player"), field="lineup.player.player")
        player_obj = Player(
            id=stable_entity_id("player", SportCode.FOOTBALL.value, str(player.get("name")), str(player.get("id"))),
            sport_id=match.sport_id,
            name=str(player.get("name")),
            country="Mockland",
            position=str(player.get("pos")) if player.get("pos") else None,
            provenance=self._provenance(
                stored,
                provider_id=_provider_id(player.get("id"), field="lineup.player"),
                event_at=None,
            ),
        )
        batch.players.append(player_obj)
        number = player.get("number")
        return LineupPlayer(
            player_id=player_obj.id,
            role=role,
            jersey_number=int(number) if number is not None else None,
            position=str(player.get("pos")) if player.get("pos") else None,
        )

    def _add_team_stats(
        self, batch: CanonicalBatch, stored: StoredRaw, match: Match, league: League, raw: object
    ) -> None:
        item = _as_dict(raw, field="statistics")
        team_raw = _as_dict(item.get("team"), field="statistics.team")
        team_id = next((team.id for team in batch.teams if team.provenance.provider_id == str(team_raw["id"])), None)
        if team_id is None:
            raise ValidationError("missing_provider_id", "Statistic team is not mapped.")
        for stat in _as_list(item.get("statistics")):
            row = _as_dict(stat, field="stat")
            value = row.get("value")
            available = value is not None
            batch.team_stats.append(
                TeamStats(
                    team_id=team_id,
                    season=league.season,
                    stat_key=slugify(str(row.get("type"))),
                    label=str(row.get("type")),
                    availability=Availability.AVAILABLE if available else Availability.UNAVAILABLE,
                    as_of=match.kickoff_at,
                    value=Decimal(str(value)) if available else None,
                    unit=None,
                    provenance=self._provenance(
                        stored,
                        provider_id=f"{match.provenance.provider_id}:{team_raw['id']}:{row.get('type')}",
                        event_at=match.kickoff_at,
                        available_at=match.kickoff_at,
                        terminal=True,
                    ),
                )
            )

    def _add_standing(self, batch: CanonicalBatch, stored: StoredRaw, sport: Sport, raw: dict[str, Any]) -> None:
        season = str(raw["season"])
        as_of = parse_rfc3339(str(raw["as_of"]))
        league_id = stable_entity_id("league", SportCode.FOOTBALL.value, "Mock Premier League", season)
        for row in _as_list(raw.get("table")):
            item = _as_dict(row, field="standing.row")
            team_raw = _as_dict(item.get("team"), field="standing.team")
            team = self._team(
                stored,
                sport,
                League(
                    id=league_id,
                    sport_id=sport.id,
                    name="Mock Premier League",
                    country="Mockland",
                    season=season,
                    provenance=self._provenance(stored, provider_id=str(raw["league_id"]), event_at=None),
                ),
                team_raw,
            )
            batch.teams.append(team)
            batch.standings.append(
                StandingSnapshot(
                    league_id=league_id,
                    season=season,
                    team_id=team.id,
                    availability=Availability.AVAILABLE,
                    as_of=as_of,
                    rank=int(item["rank"]) if item.get("rank") is not None else None,
                    points=int(item["points"]) if item.get("points") is not None else None,
                    played=int(item["played"]) if item.get("played") is not None else None,
                    won=int(item["win"]) if item.get("win") is not None else None,
                    drawn=int(item["draw"]) if item.get("draw") is not None else None,
                    lost=int(item["lose"]) if item.get("lose") is not None else None,
                    goals_for=int(item["goals_for"]) if item.get("goals_for") is not None else None,
                    goals_against=int(item["goals_against"]) if item.get("goals_against") is not None else None,
                    provenance=self._provenance(
                        stored,
                        provider_id=f"{raw['league_id']}:{team_raw['id']}:{raw['as_of']}",
                        event_at=as_of,
                        available_at=as_of,
                        terminal=True,
                    ),
                )
            )

    def _add_injury(self, batch: CanonicalBatch, stored: StoredRaw, sport: Sport, raw: dict[str, Any]) -> None:
        player = _as_dict(raw.get("player"), field="injury.player")
        team = _as_dict(raw.get("team"), field="injury.team")
        observed = parse_rfc3339(str(raw["observed_at"]))
        status_key = str(raw.get("status", "unknown"))
        try:
            status = InjuryStatus(status_key)
        except ValueError as exc:
            raise ValidationError("unknown_status", f"Unmapped injury status '{status_key}'.") from exc
        player_obj = Player(
            id=stable_entity_id("player", SportCode.FOOTBALL.value, str(player.get("name")), str(player.get("id"))),
            sport_id=sport.id,
            name=str(player.get("name")),
            country="Mockland",
            provenance=self._provenance(
                stored,
                provider_id=_provider_id(player.get("id"), field="injury.player"),
                event_at=None,
            ),
        )
        batch.players.append(player_obj)
        batch.injuries.append(
            Injury(
                id=stable_entity_id("injury", _provider_id(raw.get("id"), field="injury")),
                sport_id=sport.id,
                player_id=player_obj.id,
                team_id=next(
                    (
                        team_item.id
                        for team_item in batch.teams
                        if team_item.provenance.provider_id == str(team.get("id"))
                    ),
                    None,
                ),
                status=status,
                description=str(raw.get("type")) if raw.get("type") else None,
                availability=Availability.AVAILABLE,
                provenance=self._provenance(
                    stored,
                    provider_id=_provider_id(raw.get("id"), field="injury"),
                    event_at=observed,
                    available_at=observed,
                ),
            )
        )
