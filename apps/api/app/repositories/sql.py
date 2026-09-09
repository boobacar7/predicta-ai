from datetime import date

from app.repositories.protocols import CatalogRepository, MatchRepository, SignalRepository
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


class EmptyCatalogRepository:
    def list_sports(self) -> list[Sport]:
        return []

    def list_leagues(self, *, sport: SportCode | None, query: str | None) -> list[League]:
        return []

    def get_league(self, league_id: str) -> LeagueDetail | None:
        return None

    def list_teams(self, *, sport: SportCode | None, query: str | None) -> list[Team]:
        return []

    def get_team(self, team_id: str) -> TeamDetail | None:
        return None

    def list_players(self, *, sport: SportCode | None, query: str | None) -> list[Player]:
        return []

    def get_player(self, player_id: str) -> PlayerDetail | None:
        return None


class EmptyMatchRepository:
    def list_matches(
        self,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
    ) -> list[MatchDetail]:
        return []

    def get_match(self, match_id: str) -> MatchDetail | None:
        return None


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

    def __init__(self) -> None:
        self.catalog = EmptyCatalogRepository()
        self.matches = EmptyMatchRepository()
        self.signals = EmptySignalRepository()
