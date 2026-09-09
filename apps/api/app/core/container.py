from app.core.clock import Clock
from app.core.config import Settings
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

    def _build_repos(self) -> RepositoryBundle:
        if self.settings.repository == "sql":
            from app.repositories.sql import SqlRepositoryBundle

            return SqlRepositoryBundle()
        return MockRepositoryBundle(self.clock)
