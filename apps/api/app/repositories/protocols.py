from datetime import date
from typing import Protocol

from app.schemas import (
    Insight,
    League,
    LeagueDetail,
    MatchDetail,
    MatchStatus,
    PerformanceReport,
    Pick,
    Player,
    PlayerDetail,
    Sport,
    SportCode,
    Team,
    TeamDetail,
)


class CatalogRepository(Protocol):
    def list_sports(self) -> list[Sport]: ...

    def list_leagues(self, *, sport: SportCode | None, query: str | None) -> list[League]: ...

    def get_league(self, league_id: str) -> LeagueDetail | None: ...

    def list_teams(self, *, sport: SportCode | None, query: str | None) -> list[Team]: ...

    def get_team(self, team_id: str) -> TeamDetail | None: ...

    def list_players(self, *, sport: SportCode | None, query: str | None) -> list[Player]: ...

    def get_player(self, player_id: str) -> PlayerDetail | None: ...


class MatchRepository(Protocol):
    def list_matches(
        self,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
    ) -> list[MatchDetail]: ...

    def get_match(self, match_id: str) -> MatchDetail | None: ...


class SignalRepository(Protocol):
    def list_picks(self) -> list[Pick]: ...

    def list_insights(self) -> list[Insight]: ...

    def get_performance(self) -> PerformanceReport: ...


class RepositoryBundle(Protocol):
    catalog: CatalogRepository
    matches: MatchRepository
    signals: SignalRepository
