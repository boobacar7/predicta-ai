from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.clock import Clock
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.providers.errors import (
    LiveIngestionDisabled,
    ProviderAuthError,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderUnavailable,
)
from predicta_ingestion.providers.http import HttpTransport, HttpxTransport, RetryingJsonClient, Sleeper
from predicta_ingestion.providers.leagues import V1FootballLeague, resolve_v1_leagues
from predicta_ingestion.providers.protocols import ProviderHealth, ProviderRequest
from predicta_ingestion.raw.envelope import RawEnvelope
from predicta_ingestion.secrets import redact_text

DEFAULT_BASE_URL = "https://api.sportmonks.com/v3/football"
MAX_FIXTURE_RANGE_DAYS = 100
FIXTURE_INCLUDES = "participants;scores;league.country;season;venue;state"
LEAGUE_INCLUDES = "country"
STANDINGS_INCLUDES = "participant"
PER_PAGE = 50


@dataclass(frozen=True)
class StandingsProbe:
    """Read-only Sportmonks standings check. Never persists rows."""

    competition: str
    league_slug: str
    season_id: str
    endpoint: str
    available: bool
    http_status: int | None
    row_count: int
    participant_count: int
    sample_fields: list[str]
    pit_capable: bool
    persisted: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "competition": self.competition,
            "league_slug": self.league_slug,
            "season_id": self.season_id,
            "endpoint": self.endpoint,
            "available": self.available,
            "http_status": self.http_status,
            "row_count": self.row_count,
            "participant_count": self.participant_count,
            "sample_fields": self.sample_fields,
            "pit_capable": self.pit_capable,
            "persisted": self.persisted,
            "detail": self.detail,
        }


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
        allowed = {ResourceType.FIXTURES, ResourceType.LEAGUES, ResourceType.SEASONS}
        if request.resource not in allowed:
            raise ProviderUnavailable(self.name, "V1 Sportmonks adapter only fetches leagues, seasons and fixtures.")
        leagues = resolve_v1_leagues(request.league)
        if request.resource is ResourceType.SEASONS:
            discovered: list[RawEnvelope] = []
            for league in leagues:
                discovered.extend(self._paginate_seasons(league))
            return discovered
        envelopes: list[RawEnvelope] = []
        if request.season is None:
            for league in leagues:
                envelopes.append(self._fetch_league(league))
        if request.resource is ResourceType.FIXTURES:
            envelopes.extend(self._fetch_fixtures(request, leagues))
        return envelopes

    def probe_standings(self, *, league: V1FootballLeague, season_id: str) -> StandingsProbe:
        """GET /standings/seasons/{id} once. 401/403/404 do not abort history ingest."""
        self._require_live()
        endpoint = f"/standings/seasons/{season_id}"
        try:
            envelope = self._get_envelope(
                path=endpoint,
                query={"include": STANDINGS_INCLUDES},
                resource=ResourceType.STANDINGS,
                request_key=f"sportmonks:standings:season:{season_id}",
            )
        except ProviderAuthError:
            return _standings_probe(
                league=league,
                season_id=season_id,
                endpoint=endpoint,
                available=False,
                http_status=None,
                detail="Sportmonks rejected the standings request (401/403). Not persisted.",
            )
        except ProviderRateLimited:
            return _standings_probe(
                league=league,
                season_id=season_id,
                endpoint=endpoint,
                available=False,
                http_status=429,
                detail="Sportmonks rate-limited the standings probe. Not persisted.",
            )
        except ProviderUnavailable as exc:
            return _standings_probe(
                league=league,
                season_id=season_id,
                endpoint=endpoint,
                available=False,
                http_status=_http_status_from_detail(exc.detail),
                detail=exc.detail,
            )
        payload = self._parse_json(envelope.body)
        rows = _standings_rows(payload)
        fields = sorted({key for row in rows if isinstance(row, dict) for key in row})
        participants = {
            row.get("participant_id") for row in rows if isinstance(row, dict) and row.get("participant_id") is not None
        }
        return _standings_probe(
            league=league,
            season_id=season_id,
            endpoint=endpoint,
            available=True,
            http_status=200,
            row_count=len(rows),
            participant_count=len(participants),
            sample_fields=fields,
            pit_capable=False,
            persisted=False,
            detail=(
                "Season table is a current snapshot, not point-in-time. "
                "Historical PIT would require /standings/rounds/{roundId} with available_at. "
                "Rows were not persisted."
            ),
        )

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

    def _paginate_seasons(self, league: V1FootballLeague) -> list[RawEnvelope]:
        envelopes: list[RawEnvelope] = []
        page = 1
        while True:
            query = {
                "filters": f"seasonLeagues:{league.sportmonks_id}",
                "per_page": str(PER_PAGE),
                "page": str(page),
            }
            envelope = self._get_envelope(
                path="/seasons",
                query=query,
                resource=ResourceType.SEASONS,
                request_key=f"sportmonks:seasons:{league.sportmonks_id}:p{page}",
            )
            envelopes.append(envelope)
            if not _has_more(self._parse_json(envelope.body)):
                break
            page += 1
        return envelopes

    def _fetch_fixtures(self, request: ProviderRequest, leagues: tuple[V1FootballLeague, ...]) -> list[RawEnvelope]:
        if request.season:
            return self._fetch_fixtures_by_season(request, leagues)
        start, end = _date_window(request, self._clock.now())
        return self._paginate_between(leagues, start, end, season_id=None)

    def _fetch_fixtures_by_season(
        self,
        request: ProviderRequest,
        leagues: tuple[V1FootballLeague, ...],
    ) -> list[RawEnvelope]:
        season_id = str(request.season)
        if request.since is not None or request.until is not None:
            start, end = _date_window(request, self._clock.now())
            return self._paginate_between(leagues, start, end, season_id=season_id)
        envelopes: list[RawEnvelope] = []
        for league in leagues:
            envelopes.extend(self._paginate_season(league, season_id))
        return envelopes

    def _paginate_season(self, league: V1FootballLeague, season_id: str) -> list[RawEnvelope]:
        envelopes: list[RawEnvelope] = []
        page = 1
        while True:
            path = "/fixtures"
            query = {
                "include": FIXTURE_INCLUDES,
                "filters": f"fixtureLeagues:{league.sportmonks_id};fixtureSeasons:{season_id}",
                "per_page": str(PER_PAGE),
                "page": str(page),
            }
            envelope = self._get_envelope(
                path=path,
                query=query,
                resource=ResourceType.FIXTURES,
                request_key=f"sportmonks:fixtures:season:{season_id}:{league.sportmonks_id}:p{page}",
            )
            envelopes.append(envelope)
            if not _has_more(self._parse_json(envelope.body)):
                break
            page += 1
        return envelopes

    def _paginate_between(
        self,
        leagues: tuple[V1FootballLeague, ...],
        start: datetime,
        end: datetime,
        *,
        season_id: str | None,
    ) -> list[RawEnvelope]:
        league_ids = ",".join(str(item.sportmonks_id) for item in leagues)
        envelopes: list[RawEnvelope] = []
        for window_start, window_end in _split_range(start, end, MAX_FIXTURE_RANGE_DAYS):
            start_s = window_start.date().isoformat()
            end_s = window_end.date().isoformat()
            page = 1
            while True:
                path = f"/fixtures/between/{start_s}/{end_s}"
                filters = f"fixtureLeagues:{league_ids}"
                if season_id:
                    filters = f"{filters};fixtureSeasons:{season_id}"
                query = {
                    "include": FIXTURE_INCLUDES,
                    "filters": filters,
                    "per_page": str(PER_PAGE),
                    "page": str(page),
                }
                key = f"sportmonks:fixtures:{start_s}:{end_s}:{league_ids}"
                if season_id:
                    key = f"{key}:season:{season_id}"
                envelope = self._get_envelope(
                    path=path,
                    query=query,
                    resource=ResourceType.FIXTURES,
                    request_key=f"{key}:p{page}",
                )
                envelopes.append(envelope)
                if not _has_more(self._parse_json(envelope.body)):
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


def _standings_probe(
    *,
    league: V1FootballLeague,
    season_id: str,
    endpoint: str,
    available: bool,
    http_status: int | None,
    detail: str,
    row_count: int = 0,
    participant_count: int = 0,
    sample_fields: list[str] | None = None,
    pit_capable: bool = False,
    persisted: bool = False,
) -> StandingsProbe:
    return StandingsProbe(
        competition=league.name,
        league_slug=league.slug,
        season_id=season_id,
        endpoint=endpoint,
        available=available,
        http_status=http_status,
        row_count=row_count,
        participant_count=participant_count,
        sample_fields=sample_fields or [],
        pit_capable=pit_capable,
        persisted=persisted,
        detail=detail,
    )


def _standings_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _http_status_from_detail(detail: str) -> int | None:
    if "HTTP 404" in detail:
        return 404
    if "HTTP 400" in detail:
        return 400
    if "HTTP 429" in detail:
        return 429
    return None


def _date_window(request: ProviderRequest, now: datetime) -> tuple[datetime, datetime]:
    start = request.since or datetime(now.year, now.month, now.day, tzinfo=UTC)
    end = request.until or (start + timedelta(days=7))
    if end.tzinfo is None or start.tzinfo is None:
        raise ValidationError("naive_datetime", "Sportmonks date window must be timezone-aware UTC.")
    if end < start:
        raise ValidationError("invalid_payload", "date-to must be on or after date-from.")
    return start, end


def _has_more(payload: dict[str, Any]) -> bool:
    pagination = payload.get("pagination")
    return isinstance(pagination, dict) and bool(pagination.get("has_more"))


def _split_range(start: datetime, end: datetime, max_days: int) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start
    max_span = timedelta(days=max_days)
    while cursor <= end:
        window_end = min(cursor + max_span - timedelta(seconds=1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(seconds=1)
    return windows
