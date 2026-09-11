from datetime import timedelta

from app.ai_analyst.factory import build_analyst_provider
from app.ai_analyst.service import FootballAnalystService
from app.ai_picks.config import AiPicksThresholds
from app.ai_picks.service import AiPicksEngine
from app.ai_picks.source import CanonicalMatchCandidateSource
from app.core.clock import Clock
from app.core.config import Settings
from app.match_identity.repository import (
    MatchIdentityRepository,
    ParquetArchiveMatchIdentityRepository,
    SqlMatchIdentityRepository,
)
from app.match_identity.service import MatchResolutionService
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
        self._match_identities: MatchIdentityRepository | None = None
        self._match_resolution: MatchResolutionService | None = None
        self.dashboard = DashboardService(self.repos, clock)
        self.picks = PickService(self.repos)
        self.values = ValueListService(self.repos)
        self.performance = PerformanceService(self.repos)
        self.analyst = AnalystService(self.matches, clock, settings)
        self._football_predictions: FootballPredictionService | None = None
        odds_provider: OddsProvider
        if settings.resolved_data_mode() == "mock":
            odds_provider = MockOddsProvider()
        else:
            odds_provider = LiveOddsProvider(enable_live=True, snapshots=())
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
        self._football_ai_picks: AiPicksEngine | None = None
        self._football_ai_analyst: FootballAnalystService | None = None

    def football_predictions(self) -> FootballPredictionService:
        if self._football_predictions is None:
            self._football_predictions = build_football_prediction_service(
                clock=self.clock,
                registry_dir=self.settings.football_registry_dir,
                dataset_path=self.settings.football_dataset_path,
                model_version=self.settings.football_model_version,
                prematch_dataset_path=self.settings.football_prematch_dataset_path,
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

    def match_identities(self) -> MatchIdentityRepository:
        if self._match_identities is None:
            self._match_identities = (
                SqlMatchIdentityRepository(self.settings)
                if self.settings.repository == "sql"
                else ParquetArchiveMatchIdentityRepository(
                    self.settings.football_dataset_path,
                    self.settings.football_raw_archive_dir,
                )
            )
        return self._match_identities

    def match_resolution(self) -> MatchResolutionService:
        if self._match_resolution is None:
            self._match_resolution = MatchResolutionService(self.matches, self.match_identities())
        return self._match_resolution

    def football_ai_analyst(self) -> FootballAnalystService:
        if self._football_ai_analyst is None:
            self._football_ai_analyst = FootballAnalystService(
                clock=self.clock,
                identities=self.match_identities(),
                predictions=self.football_predictions(),
                values=self.football_values(),
                provider=build_analyst_provider(self.settings),
            )
        return self._football_ai_analyst

    def football_ai_picks(self) -> AiPicksEngine:
        if self._football_ai_picks is None:
            self._football_ai_picks = AiPicksEngine(
                values=self.football_values(),
                candidates=CanonicalMatchCandidateSource(
                    self.match_identities(),
                    self.settings.ai_picks_candidate_match_ids,
                ),
                thresholds=AiPicksThresholds(
                    minimum_edge=self.settings.ai_picks_minimum_edge,
                    minimum_ev=self.settings.ai_picks_minimum_ev,
                    minimum_model_probability=self.settings.ai_picks_minimum_model_probability,
                    maximum_odds_age=timedelta(seconds=self.settings.ai_picks_maximum_odds_age_seconds),
                ),
            )
        return self._football_ai_picks

    def _build_repos(self) -> RepositoryBundle:
        if self.settings.repository == "sql":
            from app.repositories.sql import SqlRepositoryBundle

            return SqlRepositoryBundle()
        return MockRepositoryBundle(self.clock)
