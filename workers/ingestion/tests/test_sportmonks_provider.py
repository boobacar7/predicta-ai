from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlparse

import pytest
from tests.conftest import TEST_SPORTMONKS_TOKEN
from tests.sportmonks_support import ScriptedTransport, assert_no_secret_in

from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.clock import Clock
from predicta_ingestion.config import Settings
from predicta_ingestion.providers.errors import (
    LiveIngestionDisabled,
    ProviderAuthError,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderUnavailable,
)
from predicta_ingestion.providers.http import RecordedSleep, describe_http_error
from predicta_ingestion.providers.leagues import V1_FOOTBALL_LEAGUES
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.sportmonks import MAX_FIXTURE_RANGE_DAYS, SportmonksFootballProvider, _split_range


def _provider(
    clock: Clock,
    transport: ScriptedTransport,
    *,
    enable_live: bool = True,
    token: str = TEST_SPORTMONKS_TOKEN,
) -> SportmonksFootballProvider:
    return SportmonksFootballProvider(
        enable_live=enable_live,
        api_token=token,
        clock=clock,
        transport=transport,
        sleeper=RecordedSleep(),
        max_retries=2,
        timeout_seconds=5,
    )


def test_live_disabled_does_not_call_network(clock: Clock) -> None:
    transport = ScriptedTransport()
    provider = _provider(clock, transport, enable_live=False)
    with pytest.raises(LiveIngestionDisabled) as exc:
        provider.fetch(ProviderRequest(resource=ResourceType.FIXTURES, league="premier-league"))
    assert transport.calls == []
    assert_no_secret_in(exc.value)


def test_missing_token_is_not_configured(clock: Clock) -> None:
    transport = ScriptedTransport()
    provider = _provider(clock, transport, token="")
    with pytest.raises(ProviderNotConfigured) as exc:
        provider.fetch(ProviderRequest(resource=ResourceType.FIXTURES, league="premier-league"))
    assert transport.calls == []
    assert_no_secret_in(exc.value)


def test_fetch_paginates_and_uses_authorization_header(clock: Clock) -> None:
    transport = ScriptedTransport()
    provider = _provider(clock, transport)
    request = ProviderRequest(
        resource=ResourceType.FIXTURES,
        sport=SportCode.FOOTBALL,
        league="premier-league",
        since=datetime(2026, 9, 1, tzinfo=UTC),
        until=datetime(2026, 9, 14, tzinfo=UTC),
    )
    envelopes = provider.fetch(request)
    assert len(envelopes) == 3
    assert envelopes[0].resource is ResourceType.LEAGUES
    assert envelopes[1].resource is ResourceType.FIXTURES
    assert envelopes[2].resource is ResourceType.FIXTURES
    assert all(item.data_mode.value == "live" for item in envelopes)
    urls = [url for url, _headers in transport.calls]
    assert any("/leagues/8" in url for url in urls)
    assert any("page=1" in url for url in urls)
    assert any("page=2" in url for url in urls)
    for url, headers in transport.calls:
        assert "api_token" not in url
        assert headers["Authorization"] == TEST_SPORTMONKS_TOKEN
        assert_no_secret_in(url)


def test_http_401_is_auth_error_without_token(clock: Clock) -> None:
    transport = ScriptedTransport()
    transport.force_status = 401
    transport.force_body = b'{"message":"Unauthenticated."}'
    provider = _provider(clock, transport)
    with pytest.raises(ProviderAuthError) as exc:
        provider.fetch(ProviderRequest(resource=ResourceType.LEAGUES, league="premier-league"))
    assert TEST_SPORTMONKS_TOKEN not in str(exc.value)
    assert_no_secret_in(exc.value)


def test_http_429_retries_then_succeeds(clock: Clock) -> None:
    transport = ScriptedTransport()
    transport.rate_limit_remaining = 1
    sleeper = RecordedSleep()
    provider = SportmonksFootballProvider(
        enable_live=True,
        api_token=TEST_SPORTMONKS_TOKEN,
        clock=clock,
        transport=transport,
        sleeper=sleeper,
        max_retries=2,
    )
    envelopes = provider.fetch(ProviderRequest(resource=ResourceType.LEAGUES, league="premier-league"))
    assert envelopes
    assert sleeper.delays
    assert sleeper.delays[0] >= 1.0


def test_http_429_exhausted_raises_rate_limited(clock: Clock) -> None:
    transport = ScriptedTransport()
    transport.rate_limit_remaining = 10
    provider = _provider(clock, transport)
    with pytest.raises(ProviderRateLimited) as exc:
        provider.fetch(ProviderRequest(resource=ResourceType.LEAGUES, league="premier-league"))
    assert_no_secret_in(exc.value)


def test_invalid_json_is_unavailable(clock: Clock) -> None:
    transport = ScriptedTransport()
    transport.invalid_json_once = True
    provider = _provider(clock, transport)
    with pytest.raises(ProviderUnavailable) as exc:
        provider.fetch(ProviderRequest(resource=ResourceType.LEAGUES, league="premier-league"))
    assert "JSON" in str(exc.value)
    assert_no_secret_in(exc.value)


def test_settings_reads_unprefixed_sportmonks_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPORTMONKS_API_TOKEN", TEST_SPORTMONKS_TOKEN)
    settings = Settings(_env_file=None, env="test", data_mode="live", enable_live=True, sportmonks_key="")
    assert settings.sportmonks_key == TEST_SPORTMONKS_TOKEN


def test_v1_league_catalog_contains_mls_and_european_v1() -> None:
    slugs = {item.slug for item in V1_FOOTBALL_LEAGUES}
    assert slugs == {
        "mls",
        "premier-league",
        "la-liga",
        "bundesliga",
        "serie-a",
        "ligue-1",
        "champions-league",
    }


def test_fetch_fixtures_by_season_uses_documented_fixtures_filter(clock: Clock) -> None:
    transport = ScriptedTransport()
    provider = _provider(clock, transport)
    envelopes = provider.fetch(
        ProviderRequest(
            resource=ResourceType.FIXTURES,
            sport=SportCode.FOOTBALL,
            league="mls",
            season="18001",
        )
    )
    assert envelopes
    assert all(item.resource is ResourceType.FIXTURES for item in envelopes)
    urls = [url for url, _headers in transport.calls]
    assert any(urlparse(url).path.rstrip("/").endswith("/fixtures") for url in urls)
    assert any("fixtureSeasons" in unquote(url) and "18001" in unquote(url) for url in urls)
    assert any("fixtureLeagues:779" in unquote(url) for url in urls)
    assert not any("/fixtures/seasons/" in url for url in urls)
    assert all("api_token" not in url for url in urls)


def test_http_404_is_unavailable_with_endpoint_and_without_token(
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="predicta_ingestion.providers.http")
    transport = ScriptedTransport()
    transport.force_status = 404
    transport.force_body = b'{"message":"Not Found."}'
    transport.force_headers = {"X-Request-Id": "sm-req-404"}
    provider = _provider(clock, transport)
    with pytest.raises(ProviderUnavailable) as exc:
        provider.fetch(ProviderRequest(resource=ResourceType.SEASONS, sport=SportCode.FOOTBALL, league="MLS"))
    message = str(exc.value)
    assert "HTTP 404" in message
    assert "GET" in message
    assert "/seasons" in message
    assert "request_id=sm-req-404" in message
    assert TEST_SPORTMONKS_TOKEN not in message
    assert_no_secret_in(exc.value)
    assert TEST_SPORTMONKS_TOKEN not in caplog.text
    assert "GET" in caplog.text
    assert "/seasons" in caplog.text
    assert "status=404" in caplog.text
    assert "sm-req-404" in caplog.text


def test_describe_http_error_redacts_token_in_url_and_request_id() -> None:
    detail = describe_http_error(
        method="GET",
        url=f"https://api.sportmonks.com/v3/football/fixtures/seasons/18001?api_token={TEST_SPORTMONKS_TOKEN}",
        status=404,
        headers={"X-Request-Id": TEST_SPORTMONKS_TOKEN},
        token=TEST_SPORTMONKS_TOKEN,
    )
    assert TEST_SPORTMONKS_TOKEN not in detail
    assert "HTTP 404 GET /v3/football/fixtures/seasons/18001" in detail
    assert "request_id=[redacted]" in detail
    assert "api_token=" not in detail


def test_date_range_is_split_under_sportmonks_limit() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=150)
    windows = _split_range(start, end, MAX_FIXTURE_RANGE_DAYS)
    assert len(windows) >= 2
    for window_start, window_end in windows:
        assert (window_end - window_start).days <= MAX_FIXTURE_RANGE_DAYS
