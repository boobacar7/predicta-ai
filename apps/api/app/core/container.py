from app.core.clock import Clock
from app.core.config import Settings
from app.odds.providers import LiveOddsProvider, MockOddsProvider, OddsProvider
from app.odds.repository import InMemoryOddsRepository, OddsRepository
from app.odds.service import OddsService
from app.predictions.service import FootballPredictionService, build_football_prediction_service
from app.repositories.mock import MockRepositoryBundle
from app.repositories.protocols import RepositoryBundle
from app.services.application import (
    AnalystService,
    DashboardService,
    PerformanceService,
    PickService,
    ValueListService,
)
from app.services.catalog import CatalogService, MatchService
from app.value_engine.service import FootballValueService


class AppContainer:
    def __init__(self, settings: Settings, clock: Clock) -> None:
        self.settings = settings
        self.clock = clock
        self.repos: RepositoryBundle = self._build_repos()
        self.catalog = CatalogService(self.repos)
        self.matches = MatchService(self.repos)
        self.dashboard = DashboardService(self.repos, clock)
        self.picks = PickService(self.repos)
        self.values = ValueListService(self.repos)
        self.performance = PerformanceService(self.repos)
        self.analyst = AnalystService(self.matches, clock, settings)
        self._football_predictions: FootballPredictionService | None = None
        odds_provider: OddsProvider = (
            MockOddsProvider() if settings.resolved_data_mode() == "mock" else LiveOddsProvider()
        )
        odds_repository: OddsRepository
        if settings.repository == "sql":
            from app.odds.sql_repository import SqlOddsRepository

            odds_repository = SqlOddsRepository(settings)
        else:
            odds_repository = InMemoryOddsRepository()
        self.football_odds = OddsService(
            provider=odds_provider,
            repository=odds_repository,
        )
        self._football_values: FootballValueService | None = None

    def football_predictions(self) -> FootballPredictionService:
        if self._football_predictions is None:
            self._football_predictions = build_football_prediction_service(
                clock=self.clock,
                registry_dir=self.settings.football_registry_dir,
                dataset_path=self.settings.football_dataset_path,
                model_version=self.settings.football_model_version,
            )
        return self._football_predictions

    def football_values(self) -> FootballValueService:
        if self._football_values is None:
            self._football_values = FootballValueService(
                clock=self.clock,
                predictions=self.football_predictions(),
                odds=self.football_odds,
            )
        return self._football_values

    def _build_repos(self) -> RepositoryBundle:
        if self.settings.repository == "sql":
            from app.repositories.sql import SqlRepositoryBundle

            return SqlRepositoryBundle()
        return MockRepositoryBundle(self.clock)
