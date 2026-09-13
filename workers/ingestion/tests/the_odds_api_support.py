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
        self.requests_used = 100
        self.requests_remaining = 400
        self.requests_last = 10

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
        if parsed.path.rstrip("/").endswith("/v4/sports"):
            return HttpResponse(
                status_code=200,
                body=b'[{"key":"soccer_epl","active":true},{"key":"soccer_uefa_champs_league","active":true},{"key":"soccer_uefa_champs_league_qualification","active":true}]',
                headers={
                    "x-requests-remaining": str(self.requests_remaining),
                    "x-requests-used": str(self.requests_used),
                    "x-requests-last": "0",
                },
                url=url,
            )
        if "/historical/" in parsed.path:
            date = (query.get("date") or [""])[0]
            body = load_odds_fixture(_historical_fixture(parsed.path, date, self.historical_body))
            self.requests_used += self.requests_last
            self.requests_remaining = max(0, self.requests_remaining - self.requests_last)
            last = str(self.requests_last)
        elif self.current_body == "incomplete_and_missing.json":
            body = load_odds_fixture(self.current_body)
            last = "1"
        else:
            body = load_odds_fixture(self.current_body)
            last = "1"
        return HttpResponse(
            status_code=200,
            body=body,
            headers={
                "x-requests-remaining": str(self.requests_remaining),
                "x-requests-used": str(self.requests_used),
                "x-requests-last": last,
            },
            url=url,
        )


def _historical_fixture(path: str, date: str, default_body: str) -> str:
    if "soccer_uefa_champs_league_qualification" in path:
        return "soccer_ucl_qualification_historical.json"
    if "soccer_france_ligue_one" in path:
        if "2026-08-22" in date or "2026-08-23" in date or "2026-08-24" in date:
            return "soccer_ligue1_persist_near_kickoff.json"
        if "2026-08-16T15:00" in date:
            return "soccer_ligue1_historical_pilot_later.json"
        if "2026-08-16T11:00" in date:
            return "soccer_ligue1_historical_pilot.json"
        return "soccer_ligue1_historical_pilot.json"
    if "2026-08-21" in date or "2026-08-24" in date:
        return "soccer_epl_persist_near_kickoff.json"
    if "2026-08-16T15:00" in date:
        return "soccer_epl_historical_pilot_later.json"
    if "2026-08-16T11:00" in date:
        return "soccer_epl_historical_pilot.json"
    if "2026-09-08T16:05" in date:
        return "soccer_epl_historical_later.json"
    return default_body
