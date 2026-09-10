import pytest

from predicta_ingestion.canonical.enums import ResourceType
from predicta_ingestion.providers.errors import LiveIngestionDisabled, ProviderNotConfigured
from predicta_ingestion.providers.live import ApiFootballProvider, TheOddsApiProvider
from predicta_ingestion.providers.protocols import ProviderRequest


def test_live_adapter_disabled_without_flag() -> None:
    provider = ApiFootballProvider(enable_live=False, api_key="")
    with pytest.raises(LiveIngestionDisabled):
        provider.fetch(ProviderRequest(resource=ResourceType.FIXTURES))
    health = provider.health()
    assert health.connected is False


def test_live_adapter_without_key_is_not_configured() -> None:
    provider = TheOddsApiProvider(enable_live=True, api_key="")
    with pytest.raises(ProviderNotConfigured):
        provider.fetch(ProviderRequest(resource=ResourceType.ODDS))


def test_live_adapter_with_key_still_does_not_call_network() -> None:
    provider = ApiFootballProvider(enable_live=True, api_key="not-a-real-key")
    with pytest.raises(LiveIngestionDisabled):
        provider.fetch(ProviderRequest(resource=ResourceType.FIXTURES))
    assert "pending validation" in provider.health().detail
