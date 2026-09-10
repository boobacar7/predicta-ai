from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.clock import Clock
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.providers.errors import LiveIngestionDisabled, ProviderNotConfigured, ProviderUnavailable
from predicta_ingestion.providers.http import HttpTransport, HttpxTransport, RetryingJsonClient, Sleeper
from predicta_ingestion.providers.leagues import V1FootballLeague, resolve_v1_leagues
from predicta_ingestion.providers.protocols import ProviderHealth, ProviderRequest
from predicta_ingestion.raw.envelope import RawEnvelope
from predicta_ingestion.secrets import redact_text

DEFAULT_BASE_URL = "https://api.sportmonks.com/v3/football"
MAX_FIXTURE_RANGE_DAYS = 100
FIXTURE_INCLUDES = "participants;scores;league.country;season;venue;state"
LEAGUE_INCLUDES = "country"
PER_PAGE = 50


class SportmonksFootballProvider:
    """Live Sportmonks Football adapter. Refuses to run without ENABLE_LIVE and a token."""

    name = "sportmonks"

    def __init__(
        self,
        *,
        enable_live: bool,
        api_token: str,
        clock: Clock,
        transport: HttpTransport | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        sleeper: Sleeper | None = None,
    ) -> None:
        self._enable_live = enable_live
        self._token = api_token.strip()
        self._clock = clock
        self._base_url = base_url.rstrip("/")
        self._client = RetryingJsonClient(
            provider=self.name,
            token=self._token,
            transport=transport or HttpxTransport(),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            sleeper=sleeper,
        )

    def health(self) -> ProviderHealth:
        if not self._enable_live:
            return ProviderHealth(name=self.name, connected=False, detail="live ingestion disabled")
        if not self._token:
            return ProviderHealth(name=self.name, connected=False, detail="api token missing")
        return ProviderHealth(name=self.name, connected=True, detail="sportmonks football v3")

    def fetch(self, request: ProviderRequest) -> list[RawEnvelope]:
        self._require_live()
        if request.resource not in {ResourceType.FIXTURES, ResourceType.LEAGUES}:
            raise ProviderUnavailable(self.name, "V1 Sportmonks adapter only fetches leagues and fixtures.")
        leagues = resolve_v1_leagues(request.league)
        envelopes: list[RawEnvelope] = []
        for league in leagues:
            envelopes.append(self._fetch_league(league))
        if request.resource is ResourceType.FIXTURES:
            envelopes.extend(self._fetch_fixtures(request, leagues))
        return envelopes

    def _require_live(self) -> None:
        if not self._enable_live:
            raise LiveIngestionDisabled(self.name)
        if not self._token:
            raise ProviderNotConfigured(self.name)

    def _fetch_league(self, league: V1FootballLeague) -> RawEnvelope:
        path = f"/leagues/{league.sportmonks_id}"
        query = {"include": LEAGUE_INCLUDES}
        return self._get_envelope(
            path=path,
            query=query,
            resource=ResourceType.LEAGUES,
            request_key=f"sportmonks:league:{league.sportmonks_id}",
        )

    def _fetch_fixtures(self, request: ProviderRequest, leagues: tuple[V1FootballLeague, ...]) -> list[RawEnvelope]:
        start, end = _date_window(request, self._clock.now())
        league_ids = ",".join(str(item.sportmonks_id) for item in leagues)
        envelopes: list[RawEnvelope] = []
        for window_start, window_end in _split_range(start, end, MAX_FIXTURE_RANGE_DAYS):
            start_s = window_start.date().isoformat()
            end_s = window_end.date().isoformat()
            page = 1
            while True:
                path = f"/fixtures/between/{start_s}/{end_s}"
                query = {
                    "include": FIXTURE_INCLUDES,
                    "filters": f"fixtureLeagues:{league_ids}",
                    "per_page": str(PER_PAGE),
                    "page": str(page),
                }
                envelope = self._get_envelope(
                    path=path,
                    query=query,
                    resource=ResourceType.FIXTURES,
                    request_key=f"sportmonks:fixtures:{start_s}:{end_s}:{league_ids}:p{page}",
                )
                envelopes.append(envelope)
                payload = self._parse_json(envelope.body)
                pagination = payload.get("pagination") if isinstance(payload, dict) else None
                has_more = isinstance(pagination, dict) and bool(pagination.get("has_more"))
                if not has_more:
                    break
                page += 1
        return envelopes

    def _get_envelope(
        self,
        *,
        path: str,
        query: dict[str, str],
        resource: ResourceType,
        request_key: str,
    ) -> RawEnvelope:
        url = f"{self._base_url}{path}?{urlencode(query)}"
        response = self._client.get(url)
        self._parse_json(response.body)
        return RawEnvelope(
            provider=self.name,
            resource=resource,
            request_key=request_key,
            collected_at=self._clock.now(),
            data_mode=DataMode.LIVE,
            sport=SportCode.FOOTBALL,
            body=response.body,
            content_type="application/json",
            headers=response.headers,
        )

    def _parse_json(self, body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderUnavailable(self.name, "response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderUnavailable(self.name, "JSON root must be an object")
        message = payload.get("message")
        if message and "data" not in payload:
            raise ProviderUnavailable(self.name, redact_text(str(message), self._token))
        return payload


def _date_window(request: ProviderRequest, now: datetime) -> tuple[datetime, datetime]:
    start = request.since or datetime(now.year, now.month, now.day, tzinfo=UTC)
    end = request.until or (start + timedelta(days=7))
    if end.tzinfo is None or start.tzinfo is None:
        raise ValidationError("naive_datetime", "Sportmonks date window must be timezone-aware UTC.")
    if end < start:
        raise ValidationError("invalid_payload", "date-to must be on or after date-from.")
    return start, end


def _split_range(start: datetime, end: datetime, max_days: int) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start
    max_span = timedelta(days=max_days)
    while cursor <= end:
        window_end = min(cursor + max_span - timedelta(seconds=1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(seconds=1)
    return windows
