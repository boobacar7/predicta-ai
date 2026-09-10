from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

from tests.conftest import SPORTMONKS_FIXTURES, TEST_SPORTMONKS_TOKEN

from predicta_ingestion.providers.http import HttpResponse


def load_sportmonks(name: str) -> bytes:
    return (SPORTMONKS_FIXTURES / name).read_bytes()


def _filter_value(filters: str, key: str) -> str | None:
    for part in filters.split(";"):
        if part.startswith(f"{key}:"):
            return part.split(":", 1)[1]
    return None


class ScriptedTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._league_hits = 0
        self._fixture_pages: dict[str, int] = {}
        self.force_status: int | None = None
        self.force_body: bytes = b"{}"
        self.force_headers: dict[str, str] = {}
        self.invalid_json_once = False
        self.rate_limit_remaining = 0
        self.not_found_substrings: list[str] = []
        self.standings_status: int = 403

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> HttpResponse:
        del timeout
        self.calls.append((url, dict(headers)))
        if self.invalid_json_once:
            self.invalid_json_once = False
            return HttpResponse(status_code=200, body=b"{not-json", headers={}, url=url)
        if self.rate_limit_remaining > 0:
            self.rate_limit_remaining -= 1
            return HttpResponse(
                status_code=429,
                body=b'{"message":"Too Many Attempts."}',
                headers={"Retry-After": "1"},
                url=url,
            )
        if self.force_status is not None:
            return HttpResponse(
                status_code=self.force_status,
                body=self.force_body,
                headers=self.force_headers,
                url=url,
            )
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        path = parsed.path.rstrip("/")
        filters = unquote((query.get("filters") or [""])[0])
        if self.not_found_substrings and any(needle in path for needle in self.not_found_substrings):
            return HttpResponse(
                status_code=404,
                body=b'{"message":"Not Found."}',
                headers={"X-Request-Id": "sm-test-404"},
                url=url,
            )
        if "/fixtures/seasons/" in path:
            return HttpResponse(
                status_code=404,
                body=b'{"message":"Not Found."}',
                headers={"X-Request-Id": "sm-test-404"},
                url=url,
            )
        if "/standings/" in path:
            if self.standings_status == 200:
                return HttpResponse(status_code=200, body=load_sportmonks("standings_season.json"), headers={}, url=url)
            return HttpResponse(
                status_code=self.standings_status,
                body=b'{"message":"This endpoint is not available on the current plan."}',
                headers={"X-Request-Id": "sm-test-standings"},
                url=url,
            )
        if path.endswith("/seasons"):
            league_id = _filter_value(filters, "seasonLeagues")
            filename = {
                "779": "seasons_mls.json",
                "8": "seasons_premier_league.json",
            }.get(league_id or "", "seasons_mls.json")
            return HttpResponse(status_code=200, body=load_sportmonks(filename), headers={}, url=url)
        if "/leagues/" in path:
            filename = "league_mls.json" if path.endswith("/779") else "league_premier_league.json"
            return HttpResponse(status_code=200, body=load_sportmonks(filename), headers={}, url=url)
        season_id = _filter_value(filters, "fixtureSeasons")
        if path.endswith("/fixtures") and season_id:
            filename = {
                "18000": "mls_fixtures_2023.json",
                "18001": "mls_fixtures_2024.json",
                "18002": "mls_fixtures_2025.json",
                "18003": "mls_fixtures_quarantine.json",
            }.get(season_id, "empty_fixtures.json")
            return HttpResponse(status_code=200, body=load_sportmonks(filename), headers={}, url=url)
        if "779" in filters:
            return HttpResponse(status_code=200, body=load_sportmonks("mls_fixtures_2024.json"), headers={}, url=url)
        page = (query.get("page") or ["1"])[0]
        filename = "fixtures_page2.json" if page == "2" else "fixtures_page1.json"
        return HttpResponse(status_code=200, body=load_sportmonks(filename), headers={}, url=url)


def assert_no_secret_in(value: object) -> None:
    text = str(value)
    assert TEST_SPORTMONKS_TOKEN not in text
    lowered = text.lower()
    if "api_token=" in lowered:
        assert "api_token=[redacted]" in lowered
