from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from predicta_ingestion.providers.errors import ProviderAuthError, ProviderRateLimited, ProviderUnavailable
from predicta_ingestion.secrets import redact_text, redact_url, strip_secret_headers

Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]
    url: str


class HttpTransport(Protocol):
    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> HttpResponse: ...


class HttpxTransport:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> HttpResponse:
        client = self._client or httpx.Client()
        owns_client = self._client is None
        try:
            response = client.get(url, headers=headers, timeout=timeout)
            return HttpResponse(
                status_code=response.status_code,
                body=response.content,
                headers={key: value for key, value in response.headers.items()},
                url=str(response.url),
            )
        finally:
            if owns_client:
                client.close()


class RetryingJsonClient:
    """HTTP GET with timeout, 429/5xx retry and secret-safe errors. Never logs the token."""

    def __init__(
        self,
        *,
        provider: str,
        token: str,
        transport: HttpTransport,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        sleeper: Sleeper | None = None,
    ) -> None:
        self._provider = provider
        self._token = token
        self._transport = transport
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._sleep = sleeper or __import__("time").sleep

    def get(self, url: str) -> HttpResponse:
        headers = {"Accept": "application/json", "Authorization": self._token}
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._transport.get(url, headers=headers, timeout=self._timeout)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    raise ProviderUnavailable(self._provider, "request timed out") from self._safe(exc)
                self._sleep(self._backoff(attempt, None))
                continue
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    raise ProviderUnavailable(self._provider, "network error") from self._safe(exc)
                self._sleep(self._backoff(attempt, None))
                continue

            if response.status_code in {401, 403}:
                raise ProviderAuthError(self._provider)
            if response.status_code == 429:
                if attempt >= self._max_retries:
                    raise ProviderRateLimited(self._provider)
                self._sleep(self._backoff(attempt, response.headers))
                continue
            if response.status_code >= 500:
                if attempt >= self._max_retries:
                    raise ProviderUnavailable(self._provider, f"HTTP {response.status_code}")
                self._sleep(self._backoff(attempt, response.headers))
                continue
            if response.status_code >= 400:
                raise ProviderUnavailable(self._provider, f"HTTP {response.status_code}")
            return HttpResponse(
                status_code=response.status_code,
                body=response.body,
                headers=strip_secret_headers(response.headers),
                url=redact_url(response.url, self._token),
            )
        raise ProviderUnavailable(self._provider, "exhausted retries") from last_error

    def _backoff(self, attempt: int, headers: dict[str, str] | None) -> float:
        retry_after = _retry_after_seconds(headers or {})
        exponential = min(8.0, 0.5 * (2**attempt))
        return float(max(retry_after, exponential))

    def _safe(self, exc: BaseException) -> Exception:
        return Exception(redact_text(str(exc), self._token))


def _retry_after_seconds(headers: dict[str, str]) -> float:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 1.0


@dataclass
class RecordedSleep:
    delays: list[float] = field(default_factory=list)

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
