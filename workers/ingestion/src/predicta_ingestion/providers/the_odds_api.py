from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.clock import Clock, to_rfc3339
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.providers.errors import (
    LiveIngestionDisabled,
    ProviderNotConfigured,
    ProviderUnavailable,
)
from predicta_ingestion.providers.http import HttpTransport, HttpxTransport, RetryingJsonClient, Sleeper
from predicta_ingestion.providers.leagues import V1FootballLeague, resolve_v1_leagues
from predicta_ingestion.providers.protocols import ProviderHealth, ProviderRequest
from predicta_ingestion.raw.envelope import RawEnvelope

DEFAULT_BASE_URL = "https://api.the-odds-api.com"
DEFAULT_REGIONS = "eu"
DEFAULT_MARKETS = "h2h"
DEFAULT_ODDS_FORMAT = "decimal"
DEFAULT_DATE_FORMAT = "iso"
LIVE_ODDS_PROVIDER = "the_odds_api"
LIVE_ODDS_SOURCE = "the-odds-api-v4"

# Sport keys verified from https://the-odds-api.com/sports-odds-data/sports-apis.html
V1_LEAGUE_SPORT_KEYS: dict[str, str] = {
    "mls": "soccer_usa_mls",
    "premier-league": "soccer_epl",
    "la-liga": "soccer_spain_la_liga",
    "bundesliga": "soccer_germany_bundesliga",
    "serie-a": "soccer_italy_serie_a",
    "ligue-1": "soccer_france_ligue_one",
    "champions-league": "soccer_uefa_champs_league",
}


class TheOddsApiProvider:
    """Live The Odds API v4 adapter. Disabled until ENABLE_LIVE and an API key are set."""

    name = LIVE_ODDS_PROVIDER

    def __init__(
        self,
        *,
        enable_live: bool,
        api_key: str,
        clock: Clock,
        transport: HttpTransport | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        sleeper: Sleeper | None = None,
        regions: str = DEFAULT_REGIONS,
    ) -> None:
        self._enable_live = enable_live
        self._token = api_key.strip()
        self._clock = clock
        self._base_url = base_url.rstrip("/")
        self._regions = regions
        self._client = RetryingJsonClient(
            provider=self.name,
            token=self._token,
            transport=transport or HttpxTransport(),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            sleeper=sleeper,
            send_authorization=False,
        )

    def health(self) -> ProviderHealth:
        if not self._enable_live:
            return ProviderHealth(name=self.name, connected=False, detail="live ingestion disabled")
        if not self._token:
            return ProviderHealth(name=self.name, connected=False, detail="api key missing")
        return ProviderHealth(name=self.name, connected=True, detail="the odds api v4 football h2h")

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]:
        self._require_live()
        if request.resource is not ResourceType.ODDS:
            raise ProviderUnavailable(self.name, "The Odds API adapter only fetches odds.")
        envelopes: list[RawEnvelope] = []
        for league in resolve_v1_leagues(request.league):
            envelopes.append(self._fetch_league(request, league))
        return envelopes

    def _fetch_league(self, request: ProviderRequest, league: V1FootballLeague) -> RawEnvelope:
        sport_key = V1_LEAGUE_SPORT_KEYS.get(league.slug)
        if sport_key is None:
            raise ValidationError("unknown_league", f"No The Odds API sport key is mapped for '{league.slug}'.")
        query: dict[str, str] = {
            "apiKey": self._token,
            "regions": self._regions,
            "markets": DEFAULT_MARKETS,
            "oddsFormat": DEFAULT_ODDS_FORMAT,
            "dateFormat": DEFAULT_DATE_FORMAT,
        }
        as_of = request.as_of
        if as_of is not None:
            query["date"] = to_rfc3339(as_of)
            path = f"/v4/historical/sports/{sport_key}/odds"
            endpoint = "historical_odds"
        else:
            path = f"/v4/sports/{sport_key}/odds"
            endpoint = "odds"
            if request.since is not None:
                query["commenceTimeFrom"] = to_rfc3339(request.since)
            if request.until is not None:
                query["commenceTimeTo"] = to_rfc3339(request.until)
        url = f"{self._base_url}{path}?{urlencode(query)}"
        response = self._client.get(url)
        body = self._wrap_body(
            response.body,
            sport_key=sport_key,
            endpoint=endpoint,
            league_slug=league.slug,
        )
        request_key = f"the_odds_api:{endpoint}:{sport_key}:{self._regions}:{DEFAULT_MARKETS}"
        if as_of is not None:
            request_key = f"{request_key}:{query['date']}"
        return RawEnvelope(
            provider=self.name,
            resource=ResourceType.ODDS,
            request_key=request_key,
            collected_at=self._clock.now(),
            data_mode=DataMode.LIVE,
            sport=SportCode.FOOTBALL,
            body=body,
            content_type="application/json",
            headers=response.headers,
        )

    def _wrap_body(self, body: bytes, *, sport_key: str, endpoint: str, league_slug: str) -> bytes:
        payload = _parse_json(body, self.name)
        snapshot_timestamp: str | None = None
        previous_timestamp: str | None = None
        next_timestamp: str | None = None
        if isinstance(payload, list):
            events = payload
        elif isinstance(payload, dict):
            data = payload.get("data")
            if not isinstance(data, list):
                raise ProviderUnavailable(self.name, "Historical odds payload data must be a list.")
            events = data
            snapshot_timestamp = _optional_str(payload.get("timestamp"))
            previous_timestamp = _optional_str(payload.get("previous_timestamp"))
            next_timestamp = _optional_str(payload.get("next_timestamp"))
        else:
            raise ProviderUnavailable(self.name, "Odds JSON root must be an array or an object.")
        wrapped = {
            "data_mode": DataMode.LIVE.value,
            "provider": self.name,
            "source": LIVE_ODDS_SOURCE,
            "sport_key": sport_key,
            "league_slug": league_slug,
            "endpoint": endpoint,
            "regions": self._regions,
            "markets": DEFAULT_MARKETS,
            "odds_format": DEFAULT_ODDS_FORMAT,
            "snapshot_timestamp": snapshot_timestamp,
            "previous_timestamp": previous_timestamp,
            "next_timestamp": next_timestamp,
            "data": events,
        }
        return json.dumps(wrapped, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _require_live(self) -> None:
        if not self._enable_live:
            raise LiveIngestionDisabled(self.name)
        if not self._token:
            raise ProviderNotConfigured(self.name)


def _parse_json(body: bytes, provider: str) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderUnavailable(provider, "response is not valid JSON") from exc


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
