from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from predicta_ingestion.providers.http import HttpResponse

ODDS_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "the_odds_api"
TEST_ODDS_API_KEY = "odds_test_secret_do_not_log"


def load_odds_fixture(name: str) -> bytes:
    return (ODDS_FIXTURES / name).read_bytes()


class OddsScriptedTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.force_status: int | None = None
        self.force_body: bytes = b"{}"
        self.current_body = "soccer_epl_odds.json"
        self.historical_body = "soccer_epl_historical.json"
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
                body=b'{"message":"Rate limit exceeded"}',
                headers={"Retry-After": "1"},
                url=url,
            )
        if self.force_status is not None:
            return HttpResponse(status_code=self.force_status, body=self.force_body, headers={}, url=url)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "/historical/" in parsed.path:
            date = (query.get("date") or [""])[0]
            body_name = self.historical_body
            if "2026-09-08T16:05" in date:
                body_name = "soccer_epl_historical_later.json"
            body = load_odds_fixture(body_name)
        elif self.current_body == "incomplete_and_missing.json":
            body = load_odds_fixture(self.current_body)
        else:
            body = load_odds_fixture(self.current_body)
        return HttpResponse(
            status_code=200,
            body=body,
            headers={
                "x-requests-remaining": "499",
                "x-requests-used": "1",
                "x-requests-last": "1",
            },
            url=url,
        )
