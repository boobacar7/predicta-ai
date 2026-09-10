from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from tests.conftest import SPORTMONKS_FIXTURES, TEST_SPORTMONKS_TOKEN

from predicta_ingestion.providers.http import HttpResponse


def load_sportmonks(name: str) -> bytes:
    return (SPORTMONKS_FIXTURES / name).read_bytes()


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
        if "/leagues/" in path:
            filename = "league_mls.json" if path.endswith("/779") else "league_premier_league.json"
            return HttpResponse(status_code=200, body=load_sportmonks(filename), headers={}, url=url)
        if "/fixtures/seasons/" in path:
            season_id = path.rsplit("/", 1)[-1]
            filename = {
                "18000": "mls_fixtures_2023.json",
                "18001": "mls_fixtures_2024.json",
                "18002": "mls_fixtures_2025.json",
                "18003": "mls_fixtures_quarantine.json",
            }.get(season_id, "empty_fixtures.json")
            return HttpResponse(status_code=200, body=load_sportmonks(filename), headers={}, url=url)
        filters = (query.get("filters") or [""])[0]
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
