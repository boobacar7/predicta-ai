from predicta_ingestion.canonical.enums import ResourceType
from predicta_ingestion.providers.errors import LiveIngestionDisabled, ProviderNotConfigured
from predicta_ingestion.providers.protocols import ProviderHealth, ProviderRequest
from predicta_ingestion.raw.envelope import RawEnvelope


class DisabledLiveAdapter:
    """Skeleton for a paid/live provider. Fetch never hits the network."""

    name = "disabled"

    def __init__(self, *, name: str, enable_live: bool, api_key: str) -> None:
        self.name = name
        self._enable_live = enable_live
        self._api_key = api_key

    def health(self) -> ProviderHealth:
        if not self._enable_live:
            return ProviderHealth(name=self.name, connected=False, detail="live ingestion disabled")
        if not self._api_key:
            return ProviderHealth(name=self.name, connected=False, detail="api key missing")
        return ProviderHealth(
            name=self.name,
            connected=False,
            detail="live HTTP client not implemented pending validation",
        )

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]:
        del request
        if not self._enable_live:
            raise LiveIngestionDisabled(self.name)
        if not self._api_key:
            raise ProviderNotConfigured(self.name)
        raise LiveIngestionDisabled(self.name)


class ApiFootballProvider(DisabledLiveAdapter):
    def __init__(self, *, enable_live: bool, api_key: str) -> None:
        super().__init__(name="api_football", enable_live=enable_live, api_key=api_key)


class SportmonksFootballProvider(DisabledLiveAdapter):
    def __init__(self, *, enable_live: bool, api_key: str) -> None:
        super().__init__(name="sportmonks", enable_live=enable_live, api_key=api_key)


class TheOddsApiProvider(DisabledLiveAdapter):
    def __init__(self, *, enable_live: bool, api_key: str) -> None:
        super().__init__(name="the_odds_api", enable_live=enable_live, api_key=api_key)


class BallDontLieProvider(DisabledLiveAdapter):
    def __init__(self, *, enable_live: bool, api_key: str) -> None:
        super().__init__(name="balldontlie", enable_live=enable_live, api_key=api_key)


class ApiTennisProvider(DisabledLiveAdapter):
    def __init__(self, *, enable_live: bool, api_key: str) -> None:
        super().__init__(name="api_tennis", enable_live=enable_live, api_key=api_key)


RESOURCE_CONTRACT: dict[str, tuple[ResourceType, ...]] = {
    "api_football": (
        ResourceType.FIXTURES,
        ResourceType.STANDINGS,
        ResourceType.MATCH_EVENTS,
        ResourceType.TEAM_STATS,
        ResourceType.PLAYER_STATS,
        ResourceType.INJURIES,
        ResourceType.LINEUPS,
    ),
    "the_odds_api": (ResourceType.ODDS,),
    "balldontlie": (ResourceType.FIXTURES, ResourceType.TEAM_STATS, ResourceType.PLAYER_STATS, ResourceType.INJURIES),
    "api_tennis": (ResourceType.FIXTURES,),
}
