from datetime import date

from app.core.errors import NotFoundError
from app.repositories.protocols import RepositoryBundle
from app.schemas import (
    League,
    LeagueDetail,
    MatchDetail,
    MatchStatus,
    Player,
    PlayerDetail,
    Sport,
    SportCode,
    Team,
    TeamDetail,
)


class CatalogService:
    def __init__(self, repos: RepositoryBundle) -> None:
        self._repos = repos

    def list_sports(self) -> list[Sport]:
        return self._repos.catalog.list_sports()

    def list_leagues(self, *, sport: SportCode | None, query: str | None) -> list[League]:
        return self._repos.catalog.list_leagues(sport=sport, query=query)

    def get_league(self, league_id: str) -> LeagueDetail:
        detail = self._repos.catalog.get_league(league_id)
        if detail is None:
            raise NotFoundError("League not found.", instance=f"/leagues/{league_id}")
        return detail

    def list_teams(self, *, sport: SportCode | None, query: str | None) -> list[Team]:
        return self._repos.catalog.list_teams(sport=sport, query=query)

    def get_team(self, team_id: str) -> TeamDetail:
        detail = self._repos.catalog.get_team(team_id)
        if detail is None:
            raise NotFoundError("Team not found.", instance=f"/teams/{team_id}")
        return detail

    def list_players(self, *, sport: SportCode | None, query: str | None) -> list[Player]:
        return self._repos.catalog.list_players(sport=sport, query=query)

    def get_player(self, player_id: str) -> PlayerDetail:
        detail = self._repos.catalog.get_player(player_id)
        if detail is None:
            raise NotFoundError("Player not found.", instance=f"/players/{player_id}")
        return detail


class MatchService:
    def __init__(self, repos: RepositoryBundle) -> None:
        self._repos = repos

    def list_matches(
        self,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
    ) -> list[MatchDetail]:
        return self._repos.matches.list_matches(
            sport=sport,
            league_id=league_id,
            match_date=match_date,
            status=status,
        )

    def get_match(self, match_id: str) -> MatchDetail:
        match = self._repos.matches.get_match(match_id)
        if match is None:
            raise NotFoundError("Match not found.", instance=f"/matches/{match_id}")
        return match
