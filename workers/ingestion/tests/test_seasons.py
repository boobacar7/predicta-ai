import json
from urllib.parse import unquote, urlparse

from tests.conftest import SPORTMONKS_FIXTURES, TEST_SPORTMONKS_TOKEN
from tests.sportmonks_support import ScriptedTransport, assert_no_secret_in

from predicta_ingestion.canonical.enums import ResourceType, SportCode
from predicta_ingestion.clock import Clock
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.providers.leagues import resolve_v1_leagues
from predicta_ingestion.providers.protocols import ProviderRequest
from predicta_ingestion.providers.seasons import parse_discovered_seasons, select_seasons
from predicta_ingestion.providers.sportmonks import SportmonksFootballProvider


def test_mls_alias_maps_to_sportmonks_id_779() -> None:
    league = resolve_v1_leagues("MLS")[0]
    assert league.slug == "mls"
    assert league.sportmonks_id == 779
    assert league.name == "Major League Soccer"


def test_parse_mls_seasons_from_canned_payload() -> None:
    payload = json.loads((SPORTMONKS_FIXTURES / "league_mls.json").read_text(encoding="utf-8"))
    league = resolve_v1_leagues("mls")[0]
    seasons = parse_discovered_seasons(payload, league)
    assert [item.name for item in seasons] == ["2023", "2024", "2025"]
    assert [item.provider_id for item in seasons] == ["18000", "18001", "18002"]


def test_european_default_selects_three_most_recent_seasons() -> None:
    payload = json.loads((SPORTMONKS_FIXTURES / "league_premier_league.json").read_text(encoding="utf-8"))
    league = resolve_v1_leagues("premier-league")[0]
    discovered = parse_discovered_seasons(payload, league)
    selected = select_seasons(discovered, league=league)
    assert [item.name for item in selected] == ["2024/2025", "2025/2026", "2026/2027"]
    assert "2023/2024" not in {item.name for item in selected}


def test_mls_default_selects_every_discovered_season() -> None:
    payload = json.loads((SPORTMONKS_FIXTURES / "league_mls.json").read_text(encoding="utf-8"))
    league = resolve_v1_leagues("mls")[0]
    discovered = parse_discovered_seasons(payload, league)
    selected = select_seasons(discovered, league=league)
    assert len(selected) == 3


def test_season_selector_by_id_and_name() -> None:
    payload = json.loads((SPORTMONKS_FIXTURES / "league_mls.json").read_text(encoding="utf-8"))
    league = resolve_v1_leagues("mls")[0]
    discovered = parse_discovered_seasons(payload, league)
    by_id = select_seasons(discovered, league=league, season="18001")
    by_name = select_seasons(discovered, league=league, season="2024")
    assert [item.provider_id for item in by_id] == ["18001"]
    assert [item.name for item in by_name] == ["2024"]


def test_unknown_season_is_not_invented() -> None:
    payload = json.loads((SPORTMONKS_FIXTURES / "league_mls.json").read_text(encoding="utf-8"))
    league = resolve_v1_leagues("mls")[0]
    discovered = parse_discovered_seasons(payload, league)
    try:
        select_seasons(discovered, league=league, season="2010")
    except ValidationError as exc:
        assert exc.reason_code == "unknown_season"
    else:
        raise AssertionError("missing seasons must not be invented")


def test_parse_mls_seasons_from_get_all_seasons_payload() -> None:
    payload = json.loads((SPORTMONKS_FIXTURES / "seasons_mls.json").read_text(encoding="utf-8"))
    league = resolve_v1_leagues("mls")[0]
    seasons = parse_discovered_seasons(payload, league)
    assert [item.name for item in seasons] == ["2023", "2024", "2025"]
    assert [item.provider_id for item in seasons] == ["18000", "18001", "18002"]


def test_season_discovery_fetch_uses_season_leagues_filter_and_hides_token(clock: Clock) -> None:
    transport = ScriptedTransport()
    provider = SportmonksFootballProvider(
        enable_live=True,
        api_token=TEST_SPORTMONKS_TOKEN,
        clock=clock,
        transport=transport,
    )
    envelopes = provider.fetch(ProviderRequest(resource=ResourceType.SEASONS, sport=SportCode.FOOTBALL, league="MLS"))
    assert envelopes[0].resource is ResourceType.SEASONS
    url, headers = transport.calls[0]
    assert urlparse(url).path.rstrip("/").endswith("/seasons")
    assert "seasonLeagues:779" in unquote(url)
    assert "api_token" not in url
    assert headers["Authorization"] == TEST_SPORTMONKS_TOKEN
    assert_no_secret_in(url)
    payload = json.loads(envelopes[0].body.decode("utf-8"))
    seasons = parse_discovered_seasons(payload, resolve_v1_leagues("mls")[0])
    assert len(seasons) == 3
