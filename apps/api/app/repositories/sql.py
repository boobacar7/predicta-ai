from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import AliasedClass, Session, aliased

from app.core.config import Settings
from app.db.models import League as LeagueRow
from app.db.models import Match as MatchRow
from app.db.models import Player as PlayerRow
from app.db.models import Sport as SportRow
from app.db.models import Team as TeamRow
from app.db.session import session_scope
from app.repositories.protocols import CatalogRepository, MatchRepository, SignalRepository
from app.repositories.sql_mapping import (
    INJURIES_UNAVAILABLE,
    PLAYER_AVAILABILITY_UNAVAILABLE,
    PLAYER_STATS_UNAVAILABLE,
    STANDING_UNAVAILABLE,
    TEAM_STATS_UNAVAILABLE,
    map_league,
    map_match,
    map_player,
    map_sport,
    map_team,
    unpublished_injury_stat,
)
from app.schemas import (
    DataQuality,
    Insight,
    League,
    LeagueDetail,
    MatchDetail,
    MatchStatus,
    ModelHealthSummary,
    PerformanceReport,
    Pick,
    Player,
    PlayerDetail,
    Sport,
    SportCode,
    Team,
    TeamDetail,
)
from app.services.projections import to_match_summary


class SqlCatalogRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._matches = SqlMatchRepository(settings)

    def list_sports(self) -> list[Sport]:
        with session_scope(self._settings) as session:
            rows = session.scalars(select(SportRow).order_by(SportRow.name, SportRow.id)).all()
            return [item for item in (map_sport(row) for row in rows) if item is not None]

    def list_leagues(self, *, sport: SportCode | None, query: str | None) -> list[League]:
        statement = select(LeagueRow, SportRow).join(SportRow, SportRow.id == LeagueRow.sport_id)
        if sport is not None:
            statement = statement.where(SportRow.code == sport)
        if query:
            statement = statement.where(LeagueRow.name.ilike(f"%{query}%"))
        statement = statement.order_by(LeagueRow.name, LeagueRow.id)
        with session_scope(self._settings) as session:
            mapped: list[League] = []
            for league, sport_row in session.execute(statement):
                item = map_league(league, sport_row)
                if item is not None:
                    mapped.append(item)
            return mapped

    def get_league(self, league_id: str) -> LeagueDetail | None:
        statement = (
            select(LeagueRow, SportRow)
            .join(SportRow, SportRow.id == LeagueRow.sport_id)
            .where(LeagueRow.id == league_id)
        )
        with session_scope(self._settings) as session:
            row = session.execute(statement).one_or_none()
            if row is None:
                return None
            league_row, sport_row = row
            league = map_league(league_row, sport_row)
            if league is None:
                return None
            recent = [
                to_match_summary(match)
                for match in self._matches.list_matches_in_session(
                    session,
                    sport=None,
                    league_id=league_id,
                    match_date=None,
                    status=None,
                    team_id=None,
                    limit=8,
                    newest_first=True,
                )
            ]
            return LeagueDetail(
                league=league,
                standing=[],
                recent_matches=recent,
                unavailable_fields=[STANDING_UNAVAILABLE],
            )

    def list_teams(self, *, sport: SportCode | None, query: str | None) -> list[Team]:
        statement = select(TeamRow, SportRow).join(SportRow, SportRow.id == TeamRow.sport_id)
        if sport is not None:
            statement = statement.where(SportRow.code == sport)
        if query:
            statement = statement.where(TeamRow.name.ilike(f"%{query}%"))
        statement = statement.order_by(TeamRow.name, TeamRow.id)
        with session_scope(self._settings) as session:
            mapped: list[Team] = []
            for team, sport_row in session.execute(statement):
                item = map_team(team, sport_row)
                if item is not None:
                    mapped.append(item)
            return mapped

    def get_team(self, team_id: str) -> TeamDetail | None:
        statement = (
            select(TeamRow, SportRow, LeagueRow)
            .join(SportRow, SportRow.id == TeamRow.sport_id)
            .join(LeagueRow, LeagueRow.id == TeamRow.league_id)
            .where(TeamRow.id == team_id)
        )
        with session_scope(self._settings) as session:
            row = session.execute(statement).one_or_none()
            if row is None:
                return None
            team_row, sport_row, league_row = row
            team = map_team(team_row, sport_row)
            league = map_league(league_row, sport_row)
            if team is None or league is None:
                return None
            recent = [
                to_match_summary(match)
                for match in self._matches.list_matches_in_session(
                    session,
                    sport=None,
                    league_id=None,
                    match_date=None,
                    status=None,
                    team_id=team_id,
                    limit=8,
                    newest_first=True,
                )
            ]
            return TeamDetail(
                team=team,
                league=league,
                recent_matches=recent,
                stats=[unpublished_injury_stat()],
                unavailable_fields=[TEAM_STATS_UNAVAILABLE, INJURIES_UNAVAILABLE],
            )

    def list_players(self, *, sport: SportCode | None, query: str | None) -> list[Player]:
        statement = select(PlayerRow, SportRow).join(SportRow, SportRow.id == PlayerRow.sport_id)
        if sport is not None:
            statement = statement.where(SportRow.code == sport)
        if query:
            statement = statement.where(PlayerRow.name.ilike(f"%{query}%"))
        statement = statement.order_by(PlayerRow.name, PlayerRow.id)
        with session_scope(self._settings) as session:
            mapped: list[Player] = []
            for player, sport_row in session.execute(statement):
                item = map_player(player, sport_row)
                if item is not None:
                    mapped.append(item)
            return mapped

    def get_player(self, player_id: str) -> PlayerDetail | None:
        statement = (
            select(PlayerRow, SportRow)
            .join(SportRow, SportRow.id == PlayerRow.sport_id)
            .where(PlayerRow.id == player_id)
        )
        with session_scope(self._settings) as session:
            row = session.execute(statement).one_or_none()
            if row is None:
                return None
            player_row, sport_row = row
            player = map_player(player_row, sport_row)
            if player is None:
                return None
            team: Team | None = None
            if player_row.team_id is not None:
                team_statement = (
                    select(TeamRow, SportRow)
                    .join(SportRow, SportRow.id == TeamRow.sport_id)
                    .where(TeamRow.id == player_row.team_id)
                )
                team_row = session.execute(team_statement).one_or_none()
                if team_row is not None:
                    team = map_team(team_row[0], team_row[1])
            return PlayerDetail(
                player=player,
                team=team,
                stats=[],
                recent_mentions=[],
                unavailable_fields=[PLAYER_STATS_UNAVAILABLE, PLAYER_AVAILABILITY_UNAVAILABLE],
            )


class SqlMatchRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_matches(
        self,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
    ) -> list[MatchDetail]:
        with session_scope(self._settings) as session:
            return self.list_matches_in_session(
                session,
                sport=sport,
                league_id=league_id,
                match_date=match_date,
                status=status,
                team_id=None,
                limit=None,
                newest_first=False,
            )

    def get_match(self, match_id: str) -> MatchDetail | None:
        home = aliased(TeamRow)
        away = aliased(TeamRow)
        statement = _match_join(home, away).where(MatchRow.id == match_id)
        statement = self._apply_data_mode(statement)
        with session_scope(self._settings) as session:
            row = session.execute(statement).one_or_none()
            if row is None:
                return None
            match, sport_row, league_row, home_row, away_row = row
            return map_match(match, sport_row, league_row, home_row, away_row)

    def list_matches_in_session(
        self,
        session: Session,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
        team_id: str | None,
        limit: int | None,
        newest_first: bool,
    ) -> list[MatchDetail]:
        home = aliased(TeamRow)
        away = aliased(TeamRow)
        statement = _match_join(home, away)
        statement = self._apply_data_mode(statement)
        if sport is not None:
            statement = statement.where(SportRow.code == sport)
        if league_id is not None:
            statement = statement.where(MatchRow.league_id == league_id)
        if status is not None:
            statement = statement.where(MatchRow.status == status)
        if match_date is not None:
            start = datetime_utc(match_date)
            statement = statement.where(MatchRow.kickoff_at >= start, MatchRow.kickoff_at < start + timedelta(days=1))
        if team_id is not None:
            statement = statement.where(or_(home.id == team_id, away.id == team_id))
        if newest_first:
            statement = statement.order_by(MatchRow.kickoff_at.desc(), MatchRow.id.desc())
        else:
            statement = statement.order_by(MatchRow.kickoff_at, MatchRow.id)
        if limit is not None:
            statement = statement.limit(limit)
        mapped: list[MatchDetail] = []
        for match, sport_row, league_row, home_row, away_row in session.execute(statement):
            item = map_match(match, sport_row, league_row, home_row, away_row)
            if item is not None:
                mapped.append(item)
        return mapped

    def _apply_data_mode[T](self, statement: Select[T]) -> Select[T]:
        return statement.where(MatchRow.data_mode == self._settings.resolved_data_mode())


class EmptySignalRepository:
    def list_picks(self) -> list[Pick]:
        return []

    def list_insights(self) -> list[Insight]:
        return []

    def get_performance(self) -> PerformanceReport:
        unavailable = DataQuality(
            availability="unavailable",
            source=None,
            observed_at=None,
            freshness=None,
            note="No published model metrics in the live store yet.",
        )
        return PerformanceReport(
            summary=ModelHealthSummary(
                model_version="unpublished",
                sport="football",
                window_label="No published window",
                accuracy=None,
                log_loss=None,
                brier_score=None,
                ece=None,
                theoretical_roi=None,
                theoretical_max_drawdown=None,
                prediction_count=0,
                quality=unavailable,
            ),
            series=[],
            calibration=[],
            notes=["Model metrics will appear after the ML worker publishes a versioned evaluation."],
        )


class SqlRepositoryBundle:
    catalog: CatalogRepository
    matches: MatchRepository
    signals: SignalRepository

    def __init__(self, settings: Settings) -> None:
        self.catalog = SqlCatalogRepository(settings)
        self.matches = SqlMatchRepository(settings)
        self.signals = EmptySignalRepository()


def _match_join(
    home: AliasedClass[TeamRow],
    away: AliasedClass[TeamRow],
) -> Select[tuple[MatchRow, SportRow, LeagueRow, TeamRow, TeamRow]]:
    return (
        select(MatchRow, SportRow, LeagueRow, home, away)
        .join(SportRow, SportRow.id == MatchRow.sport_id)
        .join(LeagueRow, LeagueRow.id == MatchRow.league_id)
        .join(home, home.id == MatchRow.home_team_id)
        .join(away, away.id == MatchRow.away_team_id)
    )


def datetime_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)
